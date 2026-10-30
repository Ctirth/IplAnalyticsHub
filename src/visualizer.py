"""
IPL Visualizer Suite
Generates publication-quality charts and dashboards using Matplotlib and Seaborn
with a modern dark-slate sports analytics aesthetic.
"""

import os
import matplotlib
matplotlib.use("Agg")  # headless backend: safe inside the web server
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import numpy as np
import pandas as pd

# Set global dark sports aesthetic
plt.style.use('dark_background')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#334155'
plt.rcParams['axes.linewidth'] = 0.8
plt.rcParams['grid.color'] = '#1e293b'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.6

BG_COLOR = '#0b0f19'
CARD_BG = '#111827'
TEXT_MAIN = '#f8fafc'
TEXT_MUTED = '#94a3b8'
ORANGE_CAP_COLOR = '#f97316'
PURPLE_CAP_COLOR = '#a855f7'
ACCENT_BLUE = '#38bdf8'
ACCENT_GREEN = '#10b981'
ACCENT_RED = '#f43f5e'

_STATE = {"season": "2026"}

def save_fig(fig, filepath):
    """Utility to save high-res figure cleanly."""
    fig.patch.set_facecolor(BG_COLOR)
    fig.savefig(filepath, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"[CHART SAVED] {filepath}")

def plot_points_table(df_pts, output_dir):
    """Figure 1: Official Points Table with NRR Gradient and Playoff Cutoff."""
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_facecolor(CARD_BG)
    
    # Sort for horizontal bar (bottom to top)
    df_sorted = df_pts.sort_values(by="Points", ascending=True).reset_index(drop=True)
    
    # Color bars: Top 4 qualified in vibrant cyan/emerald, others in muted slate
    colors = [ACCENT_BLUE if rank <= 4 else '#475569' for rank in df_sorted["Rank"]]
    
    bars = ax.barh(df_sorted["Team"], df_sorted["Points"], color=colors, height=0.65, edgecolor='#1e293b')
    
    # Add qualification line between rank 6 and 7 (in sorted order)
    ax.axhline(y=len(df_sorted) - 4.5, color=ACCENT_RED, linestyle='--', linewidth=1.5, alpha=0.85, label='Playoff Qualification Cutoff (Top 4)')
    
    # Annotate points, NRR, and Win/Loss
    for i, bar in enumerate(bars):
        team = df_sorted.loc[i, "Team"]
        pts = df_sorted.loc[i, "Points"]
        nrr = df_sorted.loc[i, "NRR"]
        w = df_sorted.loc[i, "Won"]
        l = df_sorted.loc[i, "Lost"]
        nrr_str = f"+{nrr:.3f}" if nrr > 0 else f"{nrr:.3f}"
        
        ax.text(pts + 0.3, bar.get_y() + bar.get_height()/2, 
                f"{pts} Pts  |  {w}W-{l}L  |  NRR: {nrr_str}", 
                va='center', ha='left', fontsize=10, fontweight='bold', color=TEXT_MAIN)
        
    ax.set_xlim(0, max(df_pts["Points"]) + 4)
    ax.set_title("IPL 2026: Official League Stage Standings & Playoff Qualification".replace("2026", _STATE["season"]), fontsize=15, fontweight='bold', pad=20, color=TEXT_MAIN)
    ax.set_xlabel("Total Points (2 pts per win)", fontsize=11, color=TEXT_MUTED, labelpad=10)
    ax.legend(loc='lower right', frameon=True, facecolor='#1e293b', edgecolor='#334155', fontsize=10)
    ax.grid(axis='x')
    
    save_fig(fig, os.path.join(output_dir, "01_points_table_standings.png"))

def plot_orange_cap(df_bat, output_dir):
    """Figure 2: Orange Cap Top Run Scorers with Strike Rate."""
    top10 = df_bat.head(10).sort_values(by="Runs", ascending=True).reset_index(drop=True)
    
    fig, ax1 = plt.subplots(figsize=(12, 7))
    ax1.set_facecolor(CARD_BG)
    
    y_pos = np.arange(len(top10))
    bars = ax1.barh(y_pos, top10["Runs"], color=ORANGE_CAP_COLOR, alpha=0.85, height=0.6, label='Total Runs')
    
    # Annotate runs and 50s/100s
    for i, bar in enumerate(bars):
        runs = top10.loc[i, "Runs"]
        sr = top10.loc[i, "Strike_Rate"]
        fifties = top10.loc[i, "Fifties"]
        hundreds = top10.loc[i, "Hundreds"]
        hs = top10.loc[i, "Highest_Score"]
        
        milestone = ""
        if hundreds > 0:
            milestone += f"[{hundreds}x100s] "
        if fifties > 0:
            milestone += f"[{fifties}x50s] "
            
        ax1.text(runs + 8, bar.get_y() + bar.get_height()/2, 
                 f"{runs} runs  (SR {sr:.1f})  HS: {hs}*  {milestone}", 
                 va='center', ha='left', fontsize=9.5, fontweight='semibold', color=TEXT_MAIN)
        
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(top10["Batsman"], fontsize=11, fontweight='bold', color=TEXT_MAIN)
    ax1.set_xlim(0, max(top10["Runs"]) + 140)
    ax1.set_xlabel("Tournament Runs Scored", fontsize=11, color=TEXT_MUTED, labelpad=10)
    ax1.set_title("IPL 2026: Orange Cap Race - Top 10 Run Scorers & Strike Efficiency".replace("2026", _STATE["season"]), fontsize=15, fontweight='bold', pad=20, color=TEXT_MAIN)
    ax1.grid(axis='x')
    
    save_fig(fig, os.path.join(output_dir, "02_orange_cap_top_run_scorers.png"))

def plot_purple_cap(df_bowl, output_dir):
    """Figure 3: Purple Cap Leading Wicket Takers with Economy Rate markers."""
    top10 = df_bowl.head(10).sort_values(by="Wickets", ascending=True).reset_index(drop=True)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_facecolor(CARD_BG)
    
    y_pos = np.arange(len(top10))
    bars = ax.barh(y_pos, top10["Wickets"], color=PURPLE_CAP_COLOR, alpha=0.85, height=0.6)
    
    for i, bar in enumerate(bars):
        wkts = top10.loc[i, "Wickets"]
        econ = top10.loc[i, "Economy"]
        dot_pct = top10.loc[i, "Dot_Pct"]
        overs = top10.loc[i, "Overs"]
        
        ax.text(wkts + 0.3, bar.get_y() + bar.get_height()/2, 
                f"{wkts} Wickets  |  Econ: {econ:.2f}  |  Dots: {dot_pct:.1f}%  ({overs} ov)", 
                va='center', ha='left', fontsize=9.5, fontweight='semibold', color=TEXT_MAIN)
        
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top10["Bowler"], fontsize=11, fontweight='bold', color=TEXT_MAIN)
    ax.set_xlim(0, max(top10["Wickets"]) + 6)
    ax.set_xlabel("Total Wickets Taken", fontsize=11, color=TEXT_MUTED, labelpad=10)
    ax.set_title("IPL 2026: Purple Cap Leaderboard - Bowling Impact & Economy".replace("2026", _STATE["season"]), fontsize=15, fontweight='bold', pad=20, color=TEXT_MAIN)
    ax.grid(axis='x')
    
    save_fig(fig, os.path.join(output_dir, "03_purple_cap_leading_wickettakers.png"))

def plot_toss_impact(df_matches, output_dir):
    """Figure 4: Multi-panel Toss Strategy & Match Outcome Breakdown."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ax1.set_facecolor(CARD_BG)
    ax2.set_facecolor(CARD_BG)
    
    # 1. Toss Decision Donut
    toss_counts = df_matches["toss_decision"].value_counts().reindex(["field", "bat"]).fillna(0).astype(int)
    colors_donut = [ACCENT_BLUE, '#f59e0b']
    labels_donut = [f"Field First ({toss_counts['field']})", f"Bat First ({toss_counts['bat']})"]
    
    wedges, texts, autotexts = ax1.pie(
        toss_counts, labels=labels_donut, autopct='%1.1f%%',
        colors=colors_donut, startangle=140, pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor=BG_COLOR, linewidth=2),
        textprops=dict(color=TEXT_MAIN, fontsize=11, fontweight='bold')
    )
    for at in autotexts:
        at.set_color('#ffffff')
        at.set_fontsize(12)
    ax1.set_title("Captains' Toss Decisions in IPL 2026".replace("2026", _STATE["season"]), fontsize=13, fontweight='bold', pad=15, color=TEXT_MAIN)
    
    # 2. Match Outcome: Bat 1st vs Chase
    chase_wins = len(df_matches[df_matches["result"] == "wickets"])
    defend_wins = len(df_matches[df_matches["result"] == "runs"])
    total_m = max(chase_wins + defend_wins, 1)
    
    labels_res = ['Chasing Team Won\n(Batting 2nd)', 'Defending Team Won\n(Batting 1st)']
    counts_res = [chase_wins, defend_wins]
    pcts = [(c / total_m * 100) for c in counts_res]
    
    bars2 = ax2.bar(labels_res, pcts, color=[ACCENT_GREEN, '#6366f1'], width=0.5, edgecolor='#1e293b')
    for bar, count in zip(bars2, counts_res):
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.1f}%\n({count} matches)", 
                 ha='center', va='bottom', fontsize=11, fontweight='bold', color=TEXT_MAIN)
        
    ax2.set_ylim(0, 80)
    ax2.set_ylabel("Win Percentage (%)", fontsize=11, color=TEXT_MUTED)
    ax2.set_title("Match Outcome: Batting First vs Chasing", fontsize=13, fontweight='bold', pad=15, color=TEXT_MAIN)
    ax2.grid(axis='y')
    
    fig.suptitle("IPL 2026: The Strategic Impact of Toss and Inning Preference".replace("2026", _STATE["season"]), fontsize=16, fontweight='bold', y=1.02, color=TEXT_MAIN)
    save_fig(fig, os.path.join(output_dir, "04_toss_impact_and_match_outcomes.png"))

def plot_venue_scoring(df_matches, output_dir):
    """Figure 5: 1st Innings Scoring Patterns Across Venues (Boxplot & Distribution)."""
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_facecolor(CARD_BG)
    
    # Order venues by median first innings score
    venue_order = df_matches.groupby("venue")["first_innings_score"].median().sort_values(ascending=False).index
    
    palette = sns.color_palette("flare", len(venue_order))
    
    sns.boxplot(
        data=df_matches, y="venue", x="first_innings_score", order=venue_order,
        hue="venue", legend=False,
        palette=palette, ax=ax, width=0.55, boxprops=dict(alpha=0.75, edgecolor='#94a3b8'),
        medianprops=dict(color='#ffffff', linewidth=2.5), flierprops=dict(marker='o', markersize=4, color=ACCENT_RED)
    )
    
    sns.stripplot(
        data=df_matches, y="venue", x="first_innings_score", order=venue_order,
        color='#ffffff', alpha=0.5, size=5, jitter=0.2, ax=ax
    )
    
    ax.axvline(200, color=ACCENT_RED, linestyle=':', linewidth=1.5, label='200-Run Par Score Benchmark')
    
    ax.set_title("IPL 2026: 1st Innings Score Distribution Across Venues".replace("2026", _STATE["season"]), fontsize=15, fontweight='bold', pad=20, color=TEXT_MAIN)
    ax.set_xlabel("1st Innings Total Runs", fontsize=11, color=TEXT_MUTED, labelpad=10)
    ax.set_ylabel("Venue", fontsize=11, color=TEXT_MUTED)
    ax.legend(loc='lower right', frameon=True, facecolor='#1e293b', edgecolor='#334155', fontsize=10)
    ax.grid(axis='x')
    
    save_fig(fig, os.path.join(output_dir, "05_venue_scoring_patterns_distribution.png"))

def plot_phase_run_rate(df_phase, output_dir):
    """Figure 6: Phase-wise Run Rate and Boundary Frequency Dynamics."""
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.set_facecolor(CARD_BG)
    
    phases = df_phase["Phase"]
    x = np.arange(len(phases))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, df_phase["Run_Rate"], width, label='Run Rate (RPO)', color=ACCENT_BLUE, edgecolor='#1e293b')
    
    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width/2, df_phase["Boundary_Run_Pct"], width, label='Boundary Run %', color='#f59e0b', edgecolor='#1e293b')
    
    # Annotations
    for bar in bars1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 0.2, f"{h:.2f}", ha='center', va='bottom', fontsize=10, fontweight='bold', color=TEXT_MAIN)
        
    for bar in bars2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 0.8, f"{h:.1f}%", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#f59e0b')
        
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{p}\n(Overs {r})" for p, r in zip(df_phase["Phase"], df_phase["Overs_Range"])], fontsize=11, fontweight='bold', color=TEXT_MAIN)
    ax1.set_ylabel("Run Rate (Runs Per Over)", fontsize=11, color=ACCENT_BLUE)
    ax2.set_ylabel("Boundary Run Contribution (%)", fontsize=11, color='#f59e0b')
    ax1.set_ylim(0, max(df_phase["Run_Rate"]) + 2.5)
    ax2.set_ylim(0, 100)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, facecolor='#1e293b', edgecolor='#334155')
    
    plt.title("IPL 2026: Phase Escalation Dynamics (Powerplay vs Middle vs Death)".replace("2026", _STATE["season"]), fontsize=14, fontweight='bold', pad=20, color=TEXT_MAIN)
    ax1.grid(axis='y')
    
    save_fig(fig, os.path.join(output_dir, "06_phase_wise_run_rate_comparison.png"))

def plot_finisher_matrix(df_finishers, output_dir):
    """Figure 7: Death Overs Specialist Quadrant Matrix."""
    df_finishers = df_finishers.dropna(subset=["Balls_Per_Boundary", "Death_Strike_Rate"]).reset_index(drop=True)
    if df_finishers.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_facecolor(CARD_BG)
    
    x = df_finishers["Balls_Per_Boundary"]
    y = df_finishers["Death_Strike_Rate"]
    
    scatter = ax.scatter(x, y, s=df_finishers["Death_Runs"] * 1.5, c=df_finishers["Boundary_Run_Pct"],
                         cmap="plasma", alpha=0.85, edgecolors="#ffffff", linewidth=1.2)
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label("Boundary Run Contribution (%)", color=TEXT_MUTED, fontsize=10)
    cbar.ax.yaxis.set_tick_params(color=TEXT_MUTED)
    
    # Quadrant reference lines
    median_bpb = x.median()
    median_sr = y.median()
    ax.axvline(median_bpb, color='#475569', linestyle='--', linewidth=1)
    ax.axhline(median_sr, color='#475569', linestyle='--', linewidth=1)
    
    ax.text(min(x) + 0.1, max(y) - 5, "ELITE FINISHERS\n(High SR + Frequent Boundaries)", 
            color=ACCENT_GREEN, fontsize=9.5, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="#064e3b", ec="none", alpha=0.8))
    
    # Annotate player names
    for i, row in df_finishers.iterrows():
        ax.annotate(row["Batsman"], (row["Balls_Per_Boundary"] + 0.05, row["Death_Strike_Rate"] + 1.2),
                    fontsize=9, color=TEXT_MAIN, fontweight='semibold')
        
    ax.set_xlabel("Balls per Boundary in Death Overs (Lower = More Lethal)", fontsize=11, color=TEXT_MUTED, labelpad=10)
    ax.set_ylabel("Death Overs Strike Rate (Overs 16-20)", fontsize=11, color=TEXT_MUTED, labelpad=10)
    ax.set_title("IPL 2026: Death Overs Finisher Matrix (Min 30 balls in overs 16-20)".replace("2026", _STATE["season"]), fontsize=14, fontweight='bold', pad=20, color=TEXT_MAIN)
    ax.grid(True)
    
    save_fig(fig, os.path.join(output_dir, "07_death_overs_finisher_matrix.png"))

def plot_correlation_heatmap(df_matches, df_deliveries, output_dir):
    """Figure 8: Correlation Matrix of Match Dynamics."""
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.set_facecolor(CARD_BG)
    
    # Aggregate match level metrics for correlation
    deliv_group = df_deliveries.groupby("match_id").agg({
        "batsman_runs": "sum",
        "extra_runs": "sum",
        "is_wicket": "sum"
    }).rename(columns={"is_wicket": "total_wickets"})
    
    # Add match metrics
    m_sub = df_matches[["match_id", "first_innings_score", "second_innings_score", "result_margin"]].copy()
    m_merged = m_sub.merge(deliv_group, on="match_id")
    m_merged["total_match_runs"] = m_merged["first_innings_score"] + m_merged["second_innings_score"]
    
    corr_features = m_merged[["first_innings_score", "second_innings_score", "total_match_runs", "total_wickets", "result_margin"]]
    corr_matrix = corr_features.corr()
    
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    cmap = sns.diverging_palette(220, 20, as_cmap=True)
    
    sns.heatmap(corr_matrix, mask=mask, cmap=cmap, vmin=-0.6, vmax=0.6, center=0,
                square=True, linewidths=1.5, annot=True, fmt=".2f",
                annot_kws={"size": 10, "weight": "bold"}, cbar_kws={"shrink": .8}, ax=ax)
    
    ax.set_title("IPL 2026: Performance Metric Correlation Matrix".replace("2026", _STATE["season"]), fontsize=14, fontweight='bold', pad=20, color=TEXT_MAIN)
    save_fig(fig, os.path.join(output_dir, "08_correlation_heatmap_metrics.png"))

def generate_all_visualizations(df_matches, df_deliveries, df_pts, df_bat, df_bowl, df_phase, df_finishers, output_dir, season_label="2026"):
    """Generates all 8 publication-grade charts."""
    _STATE["season"] = str(season_label)
    os.makedirs(output_dir, exist_ok=True)
    plot_points_table(df_pts, output_dir)
    plot_orange_cap(df_bat, output_dir)
    plot_purple_cap(df_bowl, output_dir)
    plot_toss_impact(df_matches, output_dir)
    plot_venue_scoring(df_matches, output_dir)
    plot_phase_run_rate(df_phase, output_dir)
    plot_finisher_matrix(df_finishers, output_dir)
    plot_correlation_heatmap(df_matches, df_deliveries, output_dir)
