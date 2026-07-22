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
    # Restrict to bonds already outstanding
    # at the start of the period
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
    # Average excess return per bucket
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
    # Mean adjusted excess return
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
    # Figure layout
    #
    fig = plt.figure(figsize=(20, 10))

    gs = fig.add_gridspec(
        1,
        2,
        width_ratios=[7, 1]
    )

    ax = fig.add_subplot(gs[0])
    text_ax = fig.add_subplot(gs[1])

    text_ax.axis("off")

    methodology_text = (

        "\n$\\mathbf{Period}$: "
        f"{start_date} to {end_date}\n\n"

        "$\\mathbf{METHODOLOGY}$\n\n"

        "$\\mathbf{Excess\\, Return}$\n"

        r"$ER_i = R_i - R_{BM,i}$"

        "\n\n"

        "$\\mathbf{Adjusted\\, Excess\\, Return}$\n"

        r"$AdjER_i = \frac{ER_i}{\sigma_{BM}}$"

        "\n\n"

        "$\\mathbf{Return\\, Benchmark\\, Matching}$\n"

        "1. (Sector, Country, Maturity Bucket)\n"
        "2. Fallback: (Sector, Maturity Bucket)\n\n"

        "$\\mathbf{Benchmark\\, Standard\\, Deviation}$\n"

        r"$\sigma_{BM}$ is always calculated"
        "\n"
        "using only:\n"
        "(Sector, Maturity Bucket)\n\n"
        
        "$\\mathbf{Selection\\, Effect}$\n"

        r"$Selection_{s,b} = "
        r"\frac{1}{N}"
        r"\sum_{i \in (s,b)}"
        r"(R_i - R_{BM,i})$"

        "\n\n"

        "$\\mathbf{Adjusted\\, Selection\\, Effect}$\n"

        r"$AdjSelection_{s,b}"
        r"="
        r"\frac{1}{N}"
        r"\sum_{i \in (s,b)}"
        r"AdjER_i$"
        "\n\n"

        "$\\mathbf{Definitions}$\n"

        r"$R_i$ = Bond Total Return in EUR"
        "\n"

        r"$R_{BM,i}$ = Matched Benchmark Return"
        "\n"

        r"$ER_i$ = Excess Return"
        "\n"

        r"$AdjER_i$ = Adjusted Excess Return"
        "\n"

        r"$\sigma_{BM}$ = Benchmark Return"
        "\nStandard Deviation"
        "\n\n"

        "$\\mathbf{Heatmap}$\n"

        "Color = Average Excess Return (bp)\n"
        "Line 1 = Average Excess Return\n"
        "Line 2 = Average Adjusted Excess Return\n"
        "Line 3 = Number of Bonds"
    )

    text_ax.text(
        0.0,
        1.0,
        methodology_text,
        va="top",
        ha="left",
        fontsize=14,
    )

    #
    # Heatmap
    #
    heatmap = sns.heatmap(
        selection_df,
        ax=ax,
        cmap="RdYlGn",
        norm=norm,
        annot=annotations,
        fmt="",
        linewidths=0.5,
        annot_kws={"size": 13}
    )

    cbar = heatmap.collections[0].colorbar
    cbar.ax.tick_params(labelsize=14)

    cbar.set_label(
        "Average Excess Return (bp)",
        fontsize=14,
    )

    ax.set_title(
        "Bond Selection Analysis by Sector and Maturity Bucket", fontsize=16
    )

    ax.set_xlabel("Maturity Bucket", fontsize=14)
    ax.set_ylabel("BCLASS Level 1", fontsize=14)
    ax.tick_params(
        axis="x",
        labelsize=14,
    )
    ax.tick_params(
        axis="y",
        labelsize=14,
    )

    plt.subplots_adjust(
        left=0.06,
        right=0.98,
        top=0.95,
        bottom=0.08,
        wspace=-0.1,
    )

    filename = (
        OUTPUT_DIR
        / f"bond_selection_heatmap_"
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