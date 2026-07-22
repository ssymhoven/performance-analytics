from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import TwoSlopeNorm

from analytics.config import OUTPUT_DIR


def plot_attribution_heatmap(
    portfolio_data: pd.DataFrame,
    benchmark_data: pd.DataFrame,
    account_segment_id: int,
    start_date: str,
    end_date: str,
):

    #
    # Portfolio
    #
    df = portfolio_data.copy()

    df = df[
        df["issue_date"]
        <= datetime.strptime(start_date, "%Y-%m-%d")
    ].copy()

    df["nav_pct"] = (
        df["nav_pct"]
        / df["nav_pct"].sum()
    )

    #
    # Portfolio attribution
    #
    df["ctr_bp"] = (
        df["nav_pct"]
        * df["return"]
        * 10000
    )

    contribution_df = (
        df.groupby(
            ["bclass1", "bucket"],
            observed=False
        )["ctr_bp"]
        .sum()
        .unstack(fill_value=0)
    )

    #
    # Portfolio weights
    #
    pf_weight_df = (
        df.groupby(
            ["bclass1", "bucket"],
            observed=False
        )["nav_pct"]
        .sum()
        .unstack(fill_value=0)
    )

    pf_weight_df = (
        pf_weight_df
        .reindex_like(contribution_df)
        .fillna(0)
    )

    #
    # Weighted excess return (bp)
    #
    quality_df = (
        df.groupby(
            ["bclass1", "bucket"],
            observed=False
        )
        .apply(
            lambda x:
            (
                (
                    x["nav_pct"]
                    * x["excess_return"]
                ).sum()
                / x["nav_pct"].sum()
            ) * 10000
            if x["nav_pct"].sum() > 0
            else 0,
            include_groups=False
        )
        .unstack(fill_value=0)
    )

    quality_df = (
        quality_df
        .reindex_like(contribution_df)
        .fillna(0)
    )

    #
    # Benchmark
    #
    bm = benchmark_data.copy()

    bm["bm_ctr_bp"] = (
        bm["ctr"]
        * 10000
    )

    bm_ctr_df = (
        bm.groupby(
            ["bclass1", "bucket"],
            observed=False
        )["bm_ctr_bp"]
        .sum()
        .unstack(fill_value=0)
    )

    #
    # Benchmark weights
    #
    bm_weight_df = (
        bm.groupby(
            ["bclass1", "bucket"],
            observed=False
        )["weight"]
        .sum()
        .unstack(fill_value=0)
    )

    #
    # Weighted avg benchmark std (bp)
    #
    bm_std_df = (
        bm.groupby(
            ["bclass1", "bucket"],
            observed=False
        )
        .apply(
            lambda x:
            (
                (
                    x["weight"]
                    * x["std"]
                ).sum()
                / x["weight"].sum()
            ) * 10000
            if x["weight"].sum() > 0
            else 0,
            include_groups=False
        )
        .unstack(fill_value=0)
    )

    bm_ctr_df = (
        bm_ctr_df
        .reindex_like(contribution_df)
        .fillna(0)
    )

    bm_weight_df = (
        bm_weight_df
        .reindex_like(contribution_df)
        .fillna(0)
    )

    bm_std_df = (
        bm_std_df
        .reindex_like(contribution_df)
        .fillna(0)
    )

    #
    # Benchmark annotations
    #
    bm_annotations = pd.DataFrame(
        index=bm_ctr_df.index,
        columns=bm_ctr_df.columns,
    )

    for row in bm_ctr_df.index:
        for col in bm_ctr_df.columns:

            weight = bm_weight_df.loc[row, col]
            ctr_bp = bm_ctr_df.loc[row, col]
            std_bp = bm_std_df.loc[row, col]

            bm_annotations.loc[row, col] = (
                f"w: {weight:.1%}\n"
                f"ctr: {ctr_bp:.1f}bp\n"
                f"σ: Ø {std_bp:.1f}bp"
            )

    #
    # Portfolio annotations
    #
    portfolio_annotations = pd.DataFrame(
        index=contribution_df.index,
        columns=contribution_df.columns,
    )

    for row in contribution_df.index:
        for col in contribution_df.columns:

            weight = pf_weight_df.loc[row, col]
            ctr_bp = contribution_df.loc[row, col]
            excess_bp = quality_df.loc[row, col]

            portfolio_annotations.loc[row, col] = (
                f"{weight:.1%}\n"
                f"{ctr_bp:.1f}bp\n"
                f"{excess_bp:.1f}bp"
            )

    #
    # Color scales
    #
    bm_vmax = bm_ctr_df.values.max()
    bm_vmin = bm_ctr_df.values.min()

    portfolio_limit = max(
        abs(contribution_df.values.min()),
        abs(contribution_df.values.max())
    )

    bm_norm = TwoSlopeNorm(
        vmin=bm_vmin,
        vcenter=0,
        vmax=bm_vmax
    )

    #
    # Plot
    #
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(18, 14)
    )

    #
    # Benchmark heatmap
    #
    sns.heatmap(
        bm_ctr_df,
        ax=axes[0],
        cmap="RdYlGn",
        norm=bm_norm,
        annot=bm_annotations,
        fmt="",
        linewidths=0.5,
        cbar_kws={
            "label": "Contribution To Return (bp)"
        },
    )

    axes[0].set_title(
        "Benchmark Attribution\n"
        "Weight / Contribution To Return / Weighted Avg Std"
    )

    axes[0].set_xlabel("")
    axes[0].set_ylabel("BCLASS Level 1")

    #
    # Portfolio heatmap
    #
    sns.heatmap(
        contribution_df,
        ax=axes[1],
        cmap="RdYlGn",
        center=0,
        vmin=-portfolio_limit,
        vmax=portfolio_limit,
        annot=portfolio_annotations,
        fmt="",
        linewidths=0.5,
        cbar_kws={
            "label": "Contribution To Return (bp)"
        },
    )

    axes[1].set_title(
        "Portfolio Attribution\n"
        "Weight / Contribution To Return / Weighted Excess Return"
    )

    axes[1].set_xlabel(
        "Maturity Bucket"
    )

    axes[1].set_ylabel(
        "BCLASS Level 1"
    )

    plt.suptitle(
        f"Bond Attribution Dashboard\n"
        f"{start_date} to {end_date}",
        fontsize=16,
        y=0.99
    )

    plt.tight_layout()

    filename = (
        OUTPUT_DIR
        / f"bond_attribution_dashboard_"
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
