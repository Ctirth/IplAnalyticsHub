"""
IPL Official Analytics Web Application (Flask)
Pick any IPL season (2008 - 2026) and get leaderboards, points table,
phase analytics and charts built from Cricsheet ball-by-ball data.
"""

import math
import os
import sys
import threading

import numpy as np
from flask import Flask, render_template, jsonify, request, send_from_directory, abort

base_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(base_dir, "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

from cricsheet_loader import (
    load_official_season, normalize_season, AVAILABLE_YEARS,
    SeasonNotFoundError, DataFetchError,
)
from metrics import (
    calculate_points_table,
    compute_batting_summary,
    compute_bowling_summary,
    compute_phase_analytics,
    compute_death_overs_finishers,
    compute_venue_analytics,
)
from visualizer import generate_all_visualizations

app = Flask(__name__, template_folder="templates", static_folder="static")

# Plain calendar years only (2026 ... 2008). Cricsheet's "2007/08"-style labels
# are translated inside cricsheet_loader and never reach the UI or the disk.
SEASONS_AVAILABLE = AVAILABLE_YEARS
LATEST_SEASON = SEASONS_AVAILABLE[0]

DATA_CACHE = {}
_build_lock = threading.Lock()  # matplotlib/pyplot is not thread-safe


def clean_json(obj):
    """Convert numpy types to Python and NaN/inf to None (NaN is invalid JSON)."""
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def get_season_analytics(year):
    """Retrieves or computes the complete analytical profile for a season."""
    if year in DATA_CACHE:
        return DATA_CACHE[year]

    with _build_lock:
        if year in DATA_CACHE:  # built by another request while we waited
            return DATA_CACHE[year]

        raw_dir = os.path.join(base_dir, "data", "raw")
        figures_dir = os.path.join(base_dir, "figures", year)  # e.g. figures/2020

        # load first, so a failed load never leaves an empty folder behind
        df_matches, df_deliveries = load_official_season(season=year, output_dir=raw_dir)
        os.makedirs(figures_dir, exist_ok=True)

        df_pts = calculate_points_table(df_matches, df_deliveries)
        df_bat = compute_batting_summary(df_deliveries)
        df_bowl = compute_bowling_summary(df_deliveries)
        df_phase = compute_phase_analytics(df_deliveries)
        df_finishers = compute_death_overs_finishers(df_deliveries, min_balls=25)
        df_venue = compute_venue_analytics(df_matches, df_deliveries)

        generate_all_visualizations(
            df_matches, df_deliveries, df_pts, df_bat, df_bowl, df_phase,
            df_finishers, figures_dir, season_label=year,
        )

        final_matches = df_matches[df_matches["match_type"] == "Final"]
        final_m = final_matches.iloc[-1] if len(final_matches) else df_matches.iloc[-1]
        champion = final_m["winner"]
        runner_up = final_m["team2"] if champion == final_m["team1"] else final_m["team1"]

        result = {
            "season": year,
            "season_clean": year,
            "champion": champion,
            "runner_up": runner_up,
            "final_venue": final_m["venue"],
            "final_date": final_m["date"],
            "total_matches": len(df_matches),
            "total_deliveries": len(df_deliveries),
            "total_sixes": int((df_deliveries["batsman_runs"] == 6).sum()),
            "total_fours": int((df_deliveries["batsman_runs"] == 4).sum()),
            "orange_cap": df_bat.iloc[0].to_dict() if len(df_bat) else {},
            "purple_cap": df_bowl.iloc[0].to_dict() if len(df_bowl) else {},
            "points_table": df_pts.to_dict(orient="records"),
            "top_batters": df_bat.head(10).to_dict(orient="records"),
            "top_bowlers": df_bowl.head(10).to_dict(orient="records"),
            "phase_analytics": df_phase.to_dict(orient="records"),
            "finishers": df_finishers.head(8).to_dict(orient="records"),
            "venue_stats": df_venue.head(8).to_dict(orient="records"),
        }
        result = clean_json(result)
        DATA_CACHE[year] = result
        return result


@app.route("/")
def index():
    season = normalize_season(request.args.get("season", LATEST_SEASON)) or LATEST_SEASON
    return render_template("index.html", seasons=SEASONS_AVAILABLE, active_season=season)


@app.route("/api/season/<path:season>")
def api_season(season):
    year = normalize_season(season)  # also accepts old links such as 2020/21
    if year is None:
        return jsonify({"status": "error", "message": "Unknown season."}), 404
    try:
        return jsonify({"status": "success", "data": get_season_analytics(year)})
    except SeasonNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 404
    except DataFetchError as e:
        app.logger.error("Data fetch failed for %s: %s", year, e)
        return jsonify({"status": "error", "message": str(e)}), 503
    except Exception as e:
        app.logger.exception("Failed to build analytics for season %s", year)
        return jsonify({"status": "error",
                        "message": f"Could not build analytics for IPL {year}: {type(e).__name__}: {e}"}), 500


@app.route("/figures/<season>/<path:filename>")
def serve_figure(season, filename):
    if season not in SEASONS_AVAILABLE:
        abort(404)
    return send_from_directory(os.path.join(base_dir, "figures", season), filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")  # set HOST=0.0.0.0 to expose on your network
    print(f"IPL Analytics Hub running at http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
