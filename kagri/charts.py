"""Evaluation charts (PNG) for the report, slides and the Streamlit Results tab."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# Validated categorical palette (fixed order, one colour per agent - never cycled).
COLORS = {"random": "#3567b5", "greedy": "#c4532a", "llm_single": "#d19516", "llm_multi": "#2e7d3f"}
INK, MUTED, GRID, SURFACE = "#1c2218", "#6e6c5f", "#e6e0d1", "#fbf9f3"


def _style(ax: plt.Axes, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _money(v: float) -> str:
    sign = "−" if v < 0 else ""
    a = abs(v)
    return f"{sign}${a / 1000:.1f}k" if a >= 1000 else f"{sign}${a:.0f}"


def _save(fig: plt.Figure, path: Path) -> None:
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def profit_by_agent(df: pd.DataFrame, out: Path) -> None:
    g = df.groupby(["agent", "label"], sort=False)["profit"].agg(["mean", "std"]).reset_index()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(g))
    ax.bar(x, g["mean"], yerr=g["std"].fillna(0), width=0.6, color=[COLORS.get(a, MUTED) for a in g["agent"]],
           edgecolor=SURFACE, linewidth=2, capsize=4, error_kw={"ecolor": MUTED, "linewidth": 1})
    for i, (m, s) in enumerate(zip(g["mean"], g["std"].fillna(0))):
        ax.text(i, m + s + g["mean"].max() * 0.02, _money(m), ha="center", color=INK, fontsize=10)
    ax.set_xticks(list(x), g["label"], fontsize=9)
    ax.set_ylabel("Profit over the season (mean ± std)", color=MUTED)
    _style(ax, f"Profit per agent ({df['seed'].nunique()} seeds)")
    _save(fig, out / "profit_by_agent.png")


def profit_over_time(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for agent, sub in df.groupby("agent", sort=False):
        curves = pd.DataFrame([json.loads(c) for c in sub["daily_cash"]])
        mean = curves.mean() - 3000
        ax.plot(range(len(mean)), mean, color=COLORS.get(agent, MUTED), linewidth=2, label=sub["label"].iloc[0])
        ax.text(len(mean) - 0.6, mean.iloc[-1], " " + _money(mean.iloc[-1]), color=INK, fontsize=9, va="center")
    ax.set_xlabel("Day", color=MUTED)
    ax.set_ylabel("Profit so far (mean over seeds)", color=MUTED)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _style(ax, "Profit over the season")
    _save(fig, out / "profit_over_time.png")


def reflection_curve(refl: pd.DataFrame, out: Path) -> None:
    if refl.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for agent, sub in refl.groupby("agent", sort=False):
        m = sub.groupby("episode")["profit"].mean()
        ax.plot(m.index, m.values, color=COLORS.get(agent, MUTED), linewidth=2, marker="o", markersize=8,
                label=sub["label"].iloc[0])
        for ep, v in m.items():
            ax.annotate(_money(v), (ep, v), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9,
                        color=INK)
    ax.set_xticks(sorted(refl["episode"].unique()))
    ax.set_xlabel("Season played (lessons from earlier seasons carried forward)", color=MUTED)
    ax.set_ylabel("Profit (mean over seeds)", color=MUTED)
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "Long-term memory: profit across reflection episodes")
    _save(fig, out / "reflection.png")


def action_distribution(df: pd.DataFrame, out: Path) -> None:
    acts = ["plant", "sell", "buy_animals", "fertilise", "hands", "buy_land"]
    g = df.groupby(["agent", "label"], sort=False)[[f"n_{a}" for a in acts]].mean().reset_index()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    n = len(g)
    w = 0.8 / max(1, n)
    for i, row in g.iterrows():
        xs = [j + (i - (n - 1) / 2) * w for j in range(len(acts))]
        ax.bar(xs, [row[f"n_{a}"] for a in acts], width=w, color=COLORS.get(row["agent"], MUTED),
               edgecolor=SURFACE, linewidth=2, label=row["label"])
    ax.set_xticks(range(len(acts)), [a.replace("_", " ") for a in acts])
    ax.set_ylabel("Days per season using the action", color=MUTED)
    ax.legend(frameon=False, fontsize=9, ncol=2)
    _style(ax, "What each agent does")
    _save(fig, out / "action_distribution.png")


def cost_latency(df: pd.DataFrame, out: Path) -> None:
    g = df.groupby(["agent", "label"], sort=False).agg(tokens=("tokens", "mean"),
                                                         lat=("latency_per_decision_s", "mean"),
                                                         tools=("tool_calls", "mean")).reset_index()
    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    for ax, col, title, fmt in [(axes[0], "tokens", "LLM tokens per season", "{:.0f}"),
                                (axes[1], "lat", "Seconds per daily decision", "{:.2f}s"),
                                (axes[2], "tools", "Tool calls per season", "{:.0f}")]:
        ax.bar(range(len(g)), g[col], color=[COLORS.get(a, MUTED) for a in g["agent"]], width=0.6,
               edgecolor=SURFACE, linewidth=2)
        for i, v in enumerate(g[col]):
            ax.text(i, v, fmt.format(v), ha="center", va="bottom", fontsize=9, color=INK)
        ax.set_xticks(range(len(g)), [lbl.replace(" (", "\n(") for lbl in g["label"]], fontsize=7)
        _style(ax, title)
    _save(fig, out / "cost_latency.png")


def draw_all(df: pd.DataFrame, refl: pd.DataFrame, out: Path) -> None:
    """Write every chart into `out`."""
    profit_by_agent(df, out)
    profit_over_time(df, out)
    reflection_curve(refl, out)
    action_distribution(df, out)
    cost_latency(df, out)


def ablation_chart(summary: pd.DataFrame, out: Path) -> None:
    """Horizontal bars: profit change when one component is removed (vs the full system)."""
    s = summary[summary["variant"] != "Full system"].sort_values("mean_delta")
    full = summary.loc[summary["variant"] == "Full system", "mean_profit"].iloc[0]
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(s) + 1.6))
    ax.barh(range(len(s)), s["mean_delta"], color=COLORS["greedy"], height=0.55, edgecolor=SURFACE, linewidth=2)
    for i, (d, p) in enumerate(zip(s["mean_delta"], s["delta_pct"])):
        ax.text(d, i, f"  {_money(d)}  ({p:+.0f}%)", va="center", ha="left", fontsize=9, color="#fff",
                fontweight="bold")
    ax.set_yticks(range(len(s)), s["variant"], fontsize=9)
    ax.invert_yaxis()
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlabel(f"Profit change vs full system (mean {_money(full)})", color=MUTED)
    _style(ax, "Ablation: what each component is worth")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    _save(fig, out / "ablation.png")
