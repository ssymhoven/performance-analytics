from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import TwoSlopeNorm

from analytics.config import OUTPUT_DIR


def plot_selection_heatmap(
    portfolio_data: pd.DataFrame,
    account_segment_id: int,
    start_date: str,
    end_date: str,
):

    df = portfolio_data.copy()

    #
    # Restrict to bonds already outstanding at period start
    #
    df = df[
        df["issue_date"]
        <= datetime.strptime(start_date, "%Y-%m-%d")
    ].copy()

    #
    # Re-scale weights
    #
    df["nav_pct"] = (
        df["nav_pct"]
        / df["nav_pct"].sum()
    )

    #
    # Selection effect:
    # Sum of excess returns within each bucket
    #
    selection_df = (
        df.groupby(
            ["bclass1", "bucket"],
            observed=False,
        )["excess_return"]
        .mean()
        .mul(10000)
        .unstack(fill_value=0)
        .fillna(0)
    )

    #
    # Mean adjusted excess return (σ)
    #
    adj_excess_df = (
        df.groupby(
            ["bclass1", "bucket"],
            observed=False,
        )["adj_excess_return"]
        .mean()
        .unstack(fill_value=0)
        .fillna(0)
    )

    #
    # Number of bonds
    #
    count_df = (
        df.groupby(
            ["bclass1", "bucket"],
            observed=False,
        )["isin"]
        .count()
        .unstack(fill_value=0)
        .fillna(0)
    )

    #
    # Align matrices
    #
    adj_excess_df = (
        adj_excess_df
        .reindex_like(selection_df)
        .fillna(0)
    )

    count_df = (
        count_df
        .reindex_like(selection_df)
        .fillna(0)
    )

    #
    # Annotations
    #
    annotations = pd.DataFrame(
        index=selection_df.index,
        columns=selection_df.columns,
        dtype=object,
    )

    for row in selection_df.index:
        for col in selection_df.columns:

            excess_bp = selection_df.loc[row, col]
            mean_adj = adj_excess_df.loc[row, col]
            count = int(count_df.loc[row, col])

            annotations.loc[row, col] = (
                f"Ø {excess_bp:.1f}bp\n"
                f"Ø {mean_adj:.1f}σ\n"
                f"n={count}"
            )

    #
    # Color normalization
    #
    vmin = selection_df.values.min()
    vmax = selection_df.values.max()

    if vmin < 0 < vmax:
        norm = TwoSlopeNorm(
            vmin=vmin,
            vcenter=0,
            vmax=vmax,
        )
    else:
        norm = None

    #
    # Plot
    #
    plt.figure(figsize=(18, 10))

    sns.heatmap(
        selection_df,
        cmap="RdYlGn",
        norm=norm,
        annot=annotations,
        fmt="",
        linewidths=0.5,
        cbar_kws={
            "label": "Average Excess Return (bp)"
        },
    )

    plt.title(
        "Selection Effect Heatmap\n"
        "Color = Average Excess Return (bp)\n"
        "Text = Average Excess Return / Avg Adjusted Excess Return / Number of Bonds"
    )

    plt.xlabel("Maturity Bucket")
    plt.ylabel("BCLASS Level 1")

    plt.tight_layout()

    filename = (
        OUTPUT_DIR
        / f"selection_heatmap_"
        f"{account_segment_id}_"
        f"{start_date}_"
        f"{end_date}.png"
    )

    plt.savefig(
        filename,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()