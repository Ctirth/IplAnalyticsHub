"""
Official Cricsheet Data Ingestion Engine
Fetches real IPL ball-by-ball and match datasets from Cricsheet.org and parses
a single season into (df_matches, df_deliveries) for the analytics pipeline.

Season naming
-------------
The app and the UI always use a plain calendar year (2008 ... 2026).
Cricsheet labels some seasons differently ("2007/08", "2009/10", "2020/21"),
so `to_cricsheet_key()` translates our year into Cricsheet's label. Those
slash-style labels are NEVER used for folder or file names.
"""

import csv
import io
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd

CRICSHEET_URL = "https://cricsheet.org/downloads/ipl_csv2.zip"
CACHE_MAX_AGE_SECONDS = 12 * 3600  # re-download if a season is missing and cache is older

# IPL year -> label used inside the Cricsheet archive
_CRICSHEET_KEY_OVERRIDES = {
    2008: "2007/08",
    2010: "2009/10",
    2020: "2020/21",
}
FIRST_YEAR = 2008
LAST_YEAR = 2026
AVAILABLE_YEARS = [str(y) for y in range(LAST_YEAR, FIRST_YEAR - 1, -1)]  # newest first

# Old-style labels (bookmarks, old API calls) -> year
_LEGACY_ALIASES = {"2007/08": "2008", "2007_08": "2008",
                   "2009/10": "2010", "2009_10": "2010",
                   "2020/21": "2020", "2020_21": "2020"}


class SeasonNotFoundError(ValueError):
    """Raised when the archive has no data for the requested season."""


class DataFetchError(RuntimeError):
    """Raised when the Cricsheet archive cannot be downloaded or read."""


def normalize_season(season):
    """Return a clean year string ('2020') for any accepted input, or None."""
    s = str(season).strip()
    s = _LEGACY_ALIASES.get(s, s)
    return s if s in AVAILABLE_YEARS else None


def to_cricsheet_key(year):
    """'2020' -> '2020/21', '2008' -> '2007/08', '2023' -> '2023'."""
    y = int(year)
    return _CRICSHEET_KEY_OVERRIDES.get(y, str(y))


# ----------------------------------------------------------------------------
# Download / cache
# ----------------------------------------------------------------------------
_lock = threading.Lock()
_mem = {"zip": None, "all_matches": None, "stamp": None}


def _download(url=CRICSHEET_URL, retries=3):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[DOWNLOADING] {url} (attempt {attempt}/{retries})...")
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ipl-analytics-hub/1.1)",
                "Accept": "application/zip,*/*",
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            zipfile.ZipFile(io.BytesIO(data)).testzip()  # validate it is a real zip
            return data
        except (urllib.error.URLError, TimeoutError, OSError, zipfile.BadZipFile) as e:
            last_err = e
            time.sleep(1.5 * attempt)
    raise DataFetchError(
        f"Could not download Cricsheet data ({last_err}). Check your internet "
        f"connection, or download {url} manually and save it as data/raw/.cache/cricsheet_ipl.zip"
    )


def _write_cache(cache_path, data):
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(cache_path)))
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, cache_path)  # atomic: never leaves a half-written cache


def fetch_cricsheet_zip(cache_path=None, force_refresh=False):
    """Return a ZipFile from the local cache, downloading when needed."""
    if cache_path and os.path.exists(cache_path) and not force_refresh:
        try:
            with open(cache_path, "rb") as f:
                return zipfile.ZipFile(io.BytesIO(f.read()))
        except zipfile.BadZipFile:
            print("[CACHE CORRUPT] Removing and re-downloading...")
            os.remove(cache_path)

    try:
        data = _download()
    except DataFetchError:
        # Offline but we still have an old cache: better stale than broken.
        if cache_path and os.path.exists(cache_path):
            print("[OFFLINE] Using existing cached archive.")
            with open(cache_path, "rb") as f:
                return zipfile.ZipFile(io.BytesIO(f.read()))
        raise
    if cache_path:
        _write_cache(cache_path, data)
    return zipfile.ZipFile(io.BytesIO(data))


def _load_archive(cache_path, force_refresh=False):
    """Zip + parsed all_matches.csv, kept in memory between requests."""
    stamp = os.path.getmtime(cache_path) if cache_path and os.path.exists(cache_path) else None
    if not force_refresh and _mem["zip"] is not None and _mem["stamp"] == stamp:
        return _mem["zip"], _mem["all_matches"]

    z = fetch_cricsheet_zip(cache_path, force_refresh=force_refresh)
    if "all_matches.csv" not in z.namelist():
        raise DataFetchError("Cricsheet archive is missing all_matches.csv")
    with z.open("all_matches.csv") as f:
        all_df = pd.read_csv(f, dtype=str, keep_default_na=False)
    all_df["season"] = all_df["season"].str.strip()
    _mem.update(zip=z, all_matches=all_df,
                stamp=os.path.getmtime(cache_path) if cache_path and os.path.exists(cache_path) else None)
    return z, all_df


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------
_DELIVERY_COLS = ["match_id", "innings", "ball", "batting_team", "bowling_team", "striker",
                  "non_striker", "bowler", "runs_off_bat", "extras", "wides", "noballs",
                  "byes", "legbyes", "penalty", "wicket_type", "player_dismissed"]


def _num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def _build_deliveries(rows):
    rows = rows.reindex(columns=_DELIVERY_COLS, fill_value="").copy()
    rows["innings"] = _num(rows["innings"])
    rows = rows[rows["innings"].isin([1, 2])]  # super overs are not part of official stats

    ball_parts = rows["ball"].astype(str).str.split(".", n=1, expand=True)
    over0 = pd.to_numeric(ball_parts[0], errors="coerce").fillna(0).astype(int)
    ball_in = pd.to_numeric(ball_parts[1] if 1 in ball_parts else 0, errors="coerce").fillna(0).astype(int)
    over = over0 + 1

    runs = _num(rows["runs_off_bat"])
    extras = _num(rows["extras"])

    extra_type = np.select(
        [_num(rows["wides"]) > 0, _num(rows["noballs"]) > 0, _num(rows["legbyes"]) > 0,
         _num(rows["byes"]) > 0, _num(rows["penalty"]) > 0],
        ["wides", "noballs", "legbyes", "byes", "penalty"], default="none")

    wk = rows["wicket_type"].astype(str).str.strip()
    is_wicket = (wk != "").astype(int)

    df = pd.DataFrame({
        "match_id": rows["match_id"].astype(str).values,
        "inning": rows["innings"].values,
        "batting_team": rows["batting_team"].values,
        "bowling_team": rows["bowling_team"].values,
        "over": over.values,
        "ball": ball_in.values,
        "phase": np.select([over.values <= 6, over.values <= 15], ["Powerplay", "Middle"], default="Death"),
        "batsman": rows["striker"].values,
        "non_striker": rows["non_striker"].values,
        "bowler": rows["bowler"].values,
        "batsman_runs": runs.values,
        "extra_runs": extras.values,
        "total_runs": (runs + extras).values,
        "extra_type": extra_type,
        "is_wicket": is_wicket.values,
        "dismissal_kind": np.where(is_wicket.values == 1, wk.values, "None"),
        "player_dismissed": np.where(is_wicket.values == 1,
                                     rows["player_dismissed"].values, "None"),
    })
    return df.reset_index(drop=True)


def _read_info(z, mid):
    """Parse {mid}_info.csv into a dict (csv module handles quoted commas)."""
    info = {"teams": []}
    name = f"{mid}_info.csv"
    if name not in z.namelist():
        return info
    text = z.read(name).decode("utf-8", errors="replace")
    for parts in csv.reader(io.StringIO(text)):
        if len(parts) < 3 or parts[0] != "info":
            continue
        k, v = parts[1], ",".join(parts[2:]).strip()
        if k == "team":
            info["teams"].append(v)
        elif k in ("player_of_match",):
            info.setdefault(k, v)  # first named player
        else:
            info[k] = v
    return info


def _to_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def parse_season_data(z, target_season="2026", all_df=None):
    """
    Parse one IPL season (calendar year) from the archive.
    Returns (df_matches, df_deliveries).
    """
    year = normalize_season(target_season)
    if year is None:
        raise SeasonNotFoundError(f"Unknown season: {target_season}")
    key = to_cricsheet_key(year)

    if all_df is None:
        with z.open("all_matches.csv") as f:
            all_df = pd.read_csv(f, dtype=str, keep_default_na=False)

    # EXACT match (the old substring test made '2009' also grab '2009/10')
    rows = all_df[all_df["season"] == key]
    if rows.empty:
        raise SeasonNotFoundError(f"No data found for IPL {year} in the Cricsheet archive.")

    df_deliveries = _build_deliveries(rows)
    if df_deliveries.empty:
        raise SeasonNotFoundError(f"IPL {year} has no usable deliveries.")
    print(f"[FOUND] {df_deliveries['match_id'].nunique()} matches / {len(df_deliveries)} balls for IPL {year}")

    totals = df_deliveries.groupby(["match_id", "inning"]).agg(
        runs=("total_runs", "sum"), wkts=("is_wicket", "sum")).reset_index()
    tot = {(r.match_id, r.inning): (int(r.runs), int(r.wkts)) for r in totals.itertuples()}

    matches = []
    for mid in sorted(df_deliveries["match_id"].unique()):
        info = _read_info(z, mid)
        m_rows = df_deliveries[df_deliveries["match_id"] == mid]

        teams = info["teams"]
        if len(teams) < 2:  # fall back to ball-by-ball data
            first = m_rows[m_rows["inning"] == 1]
            second = m_rows[m_rows["inning"] == 2]
            teams = [first["batting_team"].iloc[0] if len(first) else "Team 1",
                     second["batting_team"].iloc[0] if len(second) else "Team 2"]
        team1, team2 = teams[0], teams[1]

        s1, w1 = tot.get((mid, 1), (0, 0))
        s2, w2 = tot.get((mid, 2), (0, 0))

        outcome = info.get("outcome", "").lower()
        winner = info.get("winner", "")
        if "no result" in outcome or (not winner and "tie" not in outcome and not s2):
            winner, result, margin = "No Result", "no result", 0
        elif "tie" in outcome or ("eliminator" in info and not winner):
            winner = info.get("eliminator", "") or winner
            result, margin = ("super over", 0) if winner else ("tie", 0)
            winner = winner or "Tie"
        else:
            if "winner_runs" in info:
                result, margin = "runs", _to_int(info["winner_runs"])
            elif "winner_wickets" in info:
                result, margin = "wickets", _to_int(info["winner_wickets"])
            else:
                result, margin = "runs", 0
            if not winner:  # derive from scores when metadata is missing
                winner = team1 if s1 > s2 else team2

        stage = info.get("event_stage", "")
        has_number = str(info.get("match_number", "")).strip().isdigit()
        venue = info.get("venue", "") or "Unknown Venue"
        city = info.get("city", "") or venue.split(",")[-1].strip()

        matches.append({
            "match_id": mid, "season": year, "match_type": stage or "League",
            "_has_number": has_number, "date": info.get("date", ""),
            "venue": venue, "city": city, "team1": team1, "team2": team2,
            "toss_winner": info.get("toss_winner") or team1,
            "toss_decision": (info.get("toss_decision") or "field").lower(),
            "winner": winner, "result": result, "result_margin": margin,
            "first_innings_score": s1, "first_innings_wickets": w1,
            "second_innings_score": s2, "second_innings_wickets": w2,
            "player_of_match": info.get("player_of_match", "None"),
        })

    matches.sort(key=lambda m: (m["date"], m["match_id"]))
    _label_playoffs(matches)
    for m in matches:
        m.pop("_has_number", None)
    return pd.DataFrame(matches), df_deliveries


def _label_playoffs(matches):
    """Make sure the league / playoff split and the Final are identified."""
    if any(m["match_type"] != "League" for m in matches):
        return  # Cricsheet gave explicit stages, trust them

    playoff_idx = [i for i, m in enumerate(matches) if not m["_has_number"]]
    # playoffs must be the chronological tail; otherwise fall back on count
    n = len(matches)
    if not playoff_idx or playoff_idx != list(range(n - len(playoff_idx), n)):
        playoff_idx = list(range(n - 4, n)) if n == 74 else []
    if not playoff_idx:
        matches[-1]["match_type"] = "Final"
        return

    names = {3: ["Semi Final", "Semi Final", "Final"],
             4: ["Qualifier 1", "Eliminator", "Qualifier 2", "Final"]}.get(
        len(playoff_idx), ["Playoff"] * (len(playoff_idx) - 1) + ["Final"])
    for i, name in zip(playoff_idx, names):
        matches[i]["match_type"] = name


# ----------------------------------------------------------------------------
# Public orchestrator
# ----------------------------------------------------------------------------
def load_official_season(season="2026", output_dir=None, cache_dir=None):
    """
    1. Loads (or downloads) the Cricsheet archive
    2. Extracts the given IPL year
    3. Saves ipl_<year>_matches.csv / ipl_<year>_deliveries.csv into output_dir
    """
    year = normalize_season(season)
    if year is None:
        raise SeasonNotFoundError(f"Unknown season: {season}")

    if not cache_dir and output_dir:
        cache_dir = os.path.join(output_dir, ".cache")
    cache_path = os.path.join(cache_dir, "cricsheet_ipl.zip") if cache_dir else None

    with _lock:
        z, all_df = _load_archive(cache_path)
        try:
            df_matches, df_deliveries = parse_season_data(z, year, all_df)
        except SeasonNotFoundError:
            # Cache may predate this season: refresh once if it is old enough.
            age = time.time() - os.path.getmtime(cache_path) if cache_path and os.path.exists(cache_path) else 1e9
            if age < CACHE_MAX_AGE_SECONDS:
                raise
            z, all_df = _load_archive(cache_path, force_refresh=True)
            df_matches, df_deliveries = parse_season_data(z, year, all_df)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        df_matches.to_csv(os.path.join(output_dir, f"ipl_{year}_matches.csv"), index=False)
        df_deliveries.to_csv(os.path.join(output_dir, f"ipl_{year}_deliveries.csv"), index=False)
    return df_matches, df_deliveries
