"""
IPL Analytical Engine & Metrics Computation
Calculates official points table, Net Run Rate (NRR), batting leaderboards,
bowling economy/strike rates, phase analytics, and venue trends.
"""

import pandas as pd
import numpy as np

def calculate_points_table(df_matches, df_deliveries):
    """
    Computes points table with true ICC/IPL Net Run Rate (NRR) and rules:
    - If a team is all out, overs faced/credited is taken as the full 20.0 overs.
    - No Result / Abandoned matches are awarded 1 pt each and excluded from NRR.
    - Only considers league matches (match_type == 'League').
    """
    league_matches = df_matches[df_matches["match_type"] == "League"].copy()
    valid_league_m = league_matches[league_matches["result"] != "no result"]
    
    teams = sorted(list(set(league_matches["team1"]).union(set(league_matches["team2"]))))
    
    table_data = []
    
    for team in teams:
        played = league_matches[(league_matches["team1"] == team) | (league_matches["team2"] == team)]
        won = played[played["winner"] == team]
        nr = played[played["result"] == "no result"]
        tied = played[played["result"] == "tie"]  # tie with no winner (super-over wins count as wins)
        lost = played[(played["winner"] != team) & (~played["result"].isin(["no result", "tie"]))]
        
        m_played = len(played)
        m_won = len(won)
        m_lost = len(lost)
        m_tied = len(tied)
        m_nr = len(nr)
        pts = (m_won * 2) + m_tied + m_nr
        
        # Valid match IDs for this team for NRR
        team_valid_ids = valid_league_m[(valid_league_m["team1"] == team) | (valid_league_m["team2"] == team)]["match_id"].unique()
        
        # Batting stats (with official all-out 20.0 overs quota)
        runs_scored = 0
        overs_faced = 0.0
        t_bat = df_deliveries[(df_deliveries["match_id"].isin(team_valid_ids)) & (df_deliveries["batting_team"] == team) & (df_deliveries["inning"].isin([1, 2]))]
        
        for mid in team_valid_ids:
            m_bat = t_bat[t_bat["match_id"] == mid]
            if len(m_bat) > 0:
                m_runs = m_bat["total_runs"].sum()
                runs_scored += m_runs
                wkts = m_bat["is_wicket"].sum()
                legal = len(m_bat[~m_bat["extra_type"].isin(["wides", "noballs"])])
                if wkts == 10:
                    overs_faced += 20.0
                else:
                    overs_faced += (legal // 6) + ((legal % 6) / 6.0)
                    
        # Bowling stats (with official all-out 20.0 overs quota)
        runs_conceded = 0
        overs_bowled = 0.0
        t_bowl = df_deliveries[(df_deliveries["match_id"].isin(team_valid_ids)) & (df_deliveries["bowling_team"] == team) & (df_deliveries["inning"].isin([1, 2]))]
        
        for mid in team_valid_ids:
            m_bowl = t_bowl[t_bowl["match_id"] == mid]
            if len(m_bowl) > 0:
                m_runs = m_bowl["total_runs"].sum()
                runs_conceded += m_runs
                wkts = m_bowl["is_wicket"].sum()
                legal = len(m_bowl[~m_bowl["extra_type"].isin(["wides", "noballs"])])
                if wkts == 10:
                    overs_bowled += 20.0
                else:
                    overs_bowled += (legal // 6) + ((legal % 6) / 6.0)
                    
        run_rate_for = (runs_scored / overs_faced) if overs_faced > 0 else 0
        run_rate_against = (runs_conceded / overs_bowled) if overs_bowled > 0 else 0
        nrr = run_rate_for - run_rate_against
        
        table_data.append({
            "Team": team,
            "Matches": m_played,
            "Won": m_won,
            "Lost": m_lost,
            "Tied": m_tied,
            "No_Result": m_nr,
            "Points": pts,
            "Runs_Scored": runs_scored,
            "Overs_Faced": round(overs_faced, 1),
            "Runs_Conceded": runs_conceded,
            "Overs_Bowled": round(overs_bowled, 1),
            "NRR": round(nrr, 3)
        })
        
    df_pts = pd.DataFrame(table_data)
    df_pts = df_pts.sort_values(by=["Points", "NRR"], ascending=[False, False]).reset_index(drop=True)
    df_pts.index += 1
    df_pts["Rank"] = df_pts.index
    return df_pts

def compute_batting_summary(df_deliveries):
    """
    Computes comprehensive batting metrics across all matches:
    Runs, Balls, Strike Rate, Average, 4s, 6s, 50s, 100s, Dot Ball %, Boundary %.
    """
    # Exclude wide deliveries for batsman balls faced
    valid_bat_balls = df_deliveries[df_deliveries["extra_type"] != "wides"].copy()
    
    # Aggregations per match per batsman to find 50s, 100s and HS
    match_bat = valid_bat_balls.groupby(["match_id", "batsman"])["batsman_runs"].sum().reset_index()
    
    fifties = match_bat[(match_bat["batsman_runs"] >= 50) & (match_bat["batsman_runs"] < 100)].groupby("batsman").size()
    hundreds = match_bat[match_bat["batsman_runs"] >= 100].groupby("batsman").size()
    highest_scores = match_bat.groupby("batsman")["batsman_runs"].max()
    
    # Aggregations over tournament
    innings_count = valid_bat_balls.groupby("batsman")["match_id"].nunique()
    total_runs = valid_bat_balls.groupby("batsman")["batsman_runs"].sum()
    balls_faced = valid_bat_balls.groupby("batsman").size()
    
    fours = valid_bat_balls[valid_bat_balls["batsman_runs"] == 4].groupby("batsman").size()
    sixes = valid_bat_balls[valid_bat_balls["batsman_runs"] == 6].groupby("batsman").size()
    dots = valid_bat_balls[valid_bat_balls["batsman_runs"] == 0].groupby("batsman").size()
    
    # Dismissals count
    dismissals = df_deliveries[df_deliveries["is_wicket"] == 1].groupby("player_dismissed").size()
    
    bat_df = pd.DataFrame({
        "Batsman": total_runs.index,
        "Innings": innings_count.reindex(total_runs.index).fillna(0).astype(int),
        "Runs": total_runs.values,
        "Balls": balls_faced.reindex(total_runs.index).fillna(0).astype(int),
        "Highest_Score": highest_scores.reindex(total_runs.index).fillna(0).astype(int),
        "Fours": fours.reindex(total_runs.index).fillna(0).astype(int),
        "Sixes": sixes.reindex(total_runs.index).fillna(0).astype(int),
        "Dots": dots.reindex(total_runs.index).fillna(0).astype(int),
        "Dismissals": dismissals.reindex(total_runs.index).fillna(0).astype(int),
        "Fifties": fifties.reindex(total_runs.index).fillna(0).astype(int),
        "Hundreds": hundreds.reindex(total_runs.index).fillna(0).astype(int)
    })
    
    # Derived rates
    bat_df["Strike_Rate"] = np.where(bat_df["Balls"] > 0, (bat_df["Runs"] / bat_df["Balls"]) * 100, 0.0).round(2)
    bat_df["Average"] = np.where(bat_df["Dismissals"] > 0, bat_df["Runs"] / bat_df["Dismissals"], bat_df["Runs"].astype(float)).round(2)
    bat_df["Dot_Pct"] = np.where(bat_df["Balls"] > 0, (bat_df["Dots"] / bat_df["Balls"]) * 100, 0.0).round(2)
    boundary_runs = (bat_df["Fours"] * 4) + (bat_df["Sixes"] * 6)
    bat_df["Boundary_Run_Pct"] = np.where(bat_df["Runs"] > 0, (boundary_runs / bat_df["Runs"]) * 100, 0.0).round(2)
    
    bat_df = bat_df.sort_values(by="Runs", ascending=False).reset_index(drop=True)
    bat_df.index += 1
    bat_df["Rank"] = bat_df.index
    return bat_df

def compute_bowling_summary(df_deliveries):
    """
    Computes bowling metrics across all matches:
    Overs, Wickets, Runs Conceded, Economy Rate, Bowling Average, Strike Rate, Dot Ball %.
    """
    # Exclude legbyes from bowler runs
    bowler_runs_df = df_deliveries[df_deliveries["extra_type"] != "legbyes"].copy()
    runs_conceded = bowler_runs_df.groupby("bowler")["total_runs"].sum()
    
    legal_balls = df_deliveries[~df_deliveries["extra_type"].isin(["wides", "noballs"])].copy()
    balls_bowled = legal_balls.groupby("bowler").size()
    
    # Only bowler-credited wickets (exclude run outs)
    bowler_wickets = df_deliveries[
        (df_deliveries["is_wicket"] == 1) & 
        (df_deliveries["dismissal_kind"].isin(["caught", "bowled", "lbw", "stumped", "caught and bowled"]))
    ].groupby("bowler").size()
    
    dot_balls = df_deliveries[
        (~df_deliveries["extra_type"].isin(["wides", "noballs"])) & 
        (df_deliveries["total_runs"] == 0)
    ].groupby("bowler").size()
    
    innings_count = df_deliveries.groupby("bowler")["match_id"].nunique()
    
    all_bowlers = list(balls_bowled.index)
    
    bowl_df = pd.DataFrame({
        "Bowler": all_bowlers,
        "Innings": innings_count.reindex(all_bowlers).fillna(0).astype(int),
        "Balls": balls_bowled.values,
        "Runs_Conceded": runs_conceded.reindex(all_bowlers).fillna(0).astype(int),
        "Wickets": bowler_wickets.reindex(all_bowlers).fillna(0).astype(int),
        "Dots": dot_balls.reindex(all_bowlers).fillna(0).astype(int)
    })
    
    bowl_df["Overs"] = ((bowl_df["Balls"] // 6) + (bowl_df["Balls"] % 6) / 10.0).round(1)
    decimal_overs = (bowl_df["Balls"] // 6) + ((bowl_df["Balls"] % 6) / 6.0)
    
    bowl_df["Economy"] = np.where(decimal_overs > 0, bowl_df["Runs_Conceded"] / decimal_overs, 0.0).round(2)
    bowl_df["Bowling_Average"] = np.where(bowl_df["Wickets"] > 0, bowl_df["Runs_Conceded"] / bowl_df["Wickets"], np.nan).round(2)
    bowl_df["Bowling_Strike_Rate"] = np.where(bowl_df["Wickets"] > 0, bowl_df["Balls"] / bowl_df["Wickets"], np.nan).round(2)
    bowl_df["Dot_Pct"] = np.where(bowl_df["Balls"] > 0, (bowl_df["Dots"] / bowl_df["Balls"]) * 100, 0.0).round(2)
    
    bowl_df = bowl_df.sort_values(by=["Wickets", "Economy"], ascending=[False, True]).reset_index(drop=True)
    bowl_df.index += 1
    bowl_df["Rank"] = bowl_df.index
    return bowl_df

def compute_phase_analytics(df_deliveries):
    """
    Breaks down scoring rates, boundaries, and wickets by match phase:
    Powerplay (1-6), Middle (7-15), Death (16-20).
    """
    valid_phase = df_deliveries.copy()
    
    phase_summary = []
    for phase in ["Powerplay", "Middle", "Death"]:
        phase_df = valid_phase[valid_phase["phase"] == phase]
        total_runs = phase_df["total_runs"].sum()
        legal_balls = len(phase_df[~phase_df["extra_type"].isin(["wides", "noballs"])])
        wickets = phase_df["is_wicket"].sum()
        fours = (phase_df["batsman_runs"] == 4).sum()
        sixes = (phase_df["batsman_runs"] == 6).sum()
        overs = (legal_balls // 6) + ((legal_balls % 6) / 6.0)
        
        run_rate = (total_runs / overs) if overs > 0 else 0
        boundary_pct = (((fours * 4) + (sixes * 6)) / total_runs * 100) if total_runs > 0 else 0
        balls_per_wicket = (legal_balls / wickets) if wickets > 0 else np.nan
        
        phase_summary.append({
            "Phase": phase,
            "Overs_Range": "1 - 6" if phase == "Powerplay" else ("7 - 15" if phase == "Middle" else "16 - 20"),
            "Total_Runs": total_runs,
            "Legal_Balls": legal_balls,
            "Total_Wickets": wickets,
            "Fours": fours,
            "Sixes": sixes,
            "Run_Rate": round(run_rate, 2),
            "Boundary_Run_Pct": round(boundary_pct, 2),
            "Balls_Per_Wicket": round(balls_per_wicket, 1)
        })
        
    return pd.DataFrame(phase_summary)

def compute_death_overs_finishers(df_deliveries, min_balls=30):
    """
    Isolates batsman performance in the death overs (overs 16-20).
    Calculates Death Strike Rate, Boundary %, and Balls per Boundary.
    """
    death_df = df_deliveries[(df_deliveries["phase"] == "Death") & (df_deliveries["extra_type"] != "wides")].copy()
    
    runs = death_df.groupby("batsman")["batsman_runs"].sum()
    balls = death_df.groupby("batsman").size()
    fours = death_df[death_df["batsman_runs"] == 4].groupby("batsman").size()
    sixes = death_df[death_df["batsman_runs"] == 6].groupby("batsman").size()
    
    bats = balls[balls >= min_balls].index
    if len(bats) == 0:  # small seasons / few death-over balls: relax threshold
        bats = balls.sort_values(ascending=False).head(8).index
    
    finishers = pd.DataFrame({
        "Batsman": bats,
        "Death_Balls": balls.reindex(bats).values,
        "Death_Runs": runs.reindex(bats).values,
        "Death_Fours": fours.reindex(bats).fillna(0).astype(int).values,
        "Death_Sixes": sixes.reindex(bats).fillna(0).astype(int).values
    })
    
    finishers["Death_Strike_Rate"] = ((finishers["Death_Runs"] / finishers["Death_Balls"]) * 100).round(2)
    finishers["Total_Boundaries"] = finishers["Death_Fours"] + finishers["Death_Sixes"]
    finishers["Boundary_Run_Pct"] = (((finishers["Death_Fours"] * 4) + (finishers["Death_Sixes"] * 6)) / finishers["Death_Runs"].replace(0, np.nan) * 100).round(2)
    finishers["Balls_Per_Boundary"] = (finishers["Death_Balls"] / finishers["Total_Boundaries"].replace(0, np.nan)).round(2)
    
    finishers = finishers.sort_values(by="Death_Strike_Rate", ascending=False).reset_index(drop=True)
    return finishers

def compute_venue_analytics(df_matches, df_deliveries):
    """
    Analyzes venue dynamics: average 1st innings score, chase success rate,
    highest chase, and boundary totals.
    """
    venue_stats = []
    
    for venue, group in df_matches.groupby("venue"):
        matches_count = len(group)
        avg_1st_score = group["first_innings_score"].mean()
        avg_2nd_score = group["second_innings_score"].mean()
        max_1st_score = group["first_innings_score"].max()
        min_1st_score = group["first_innings_score"].min()
        
        # Chase wins (winner was batting second)
        chase_wins = len(group[group["result"] == "wickets"])
        defend_wins = len(group[group["result"] == "runs"])
        chase_win_pct = (chase_wins / matches_count * 100) if matches_count > 0 else 0
        
        # Deliveries at this venue
        v_match_ids = set(group["match_id"])
        v_deliv = df_deliveries[df_deliveries["match_id"].isin(v_match_ids)]
        sixes = (v_deliv["batsman_runs"] == 6).sum()
        fours = (v_deliv["batsman_runs"] == 4).sum()
        
        avg_sixes_per_match = round(sixes / matches_count, 1) if matches_count > 0 else 0
        avg_fours_per_match = round(fours / matches_count, 1) if matches_count > 0 else 0
        
        venue_stats.append({
            "Venue": venue,
            "City": group["city"].iloc[0],
            "Matches": matches_count,
            "Avg_1st_Innings_Score": round(avg_1st_score, 1),
            "Avg_2nd_Innings_Score": round(avg_2nd_score, 1),
            "Highest_Score": max_1st_score,
            "Lowest_Score": min_1st_score,
            "Defend_Wins": defend_wins,
            "Chase_Wins": chase_wins,
            "Chase_Win_Pct": round(chase_win_pct, 1),
            "Avg_Sixes_Per_Match": avg_sixes_per_match,
            "Avg_Fours_Per_Match": avg_fours_per_match
        })
        
    df_venue = pd.DataFrame(venue_stats).sort_values(by="Avg_1st_Innings_Score", ascending=False).reset_index(drop=True)
    return df_venue
