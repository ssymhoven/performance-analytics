
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.ticker as mtick
import pandas as pd

from analytics.config import OUTPUT_DIR

def plot_bond_excess_return(
    portfolio_data: pd.DataFrame,
    account_segment_id: int,
    start_date: str,
    end_date: str
):

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    portfolio_data = portfolio_data.copy()

    #
    # Position categorization
    #
    portfolio_data["position_category"] = "Unchanged Position"

    mask = portfolio_data["issue_date"].between(start, end)
    portfolio_data.loc[mask, "position_category"] = "Primary Market"

    mask = (
        ~portfolio_data["issue_date"].between(start, end)
        & portfolio_data["first_buy"].between(start, end)
    )
    portfolio_data.loc[mask, "position_category"] = "Initiated"

    mask = (
        ~portfolio_data["issue_date"].between(start, end)
        & (portfolio_data["first_buy"] < start)
        & portfolio_data["latest_buy"].between(start, end)
    )
    portfolio_data.loc[mask, "position_category"] = "Added"

    mask = portfolio_data["latest_sell"].between(start, end)
    portfolio_data.loc[mask, "position_category"] = "Trimmed"

    colors = {
        "Unchanged Position": "lightgrey",
        "Primary Market": "tab:green",
        "Initiated": "tab:blue",
        "Added": "tab:orange",
        "Trimmed": "tab:red",
    }

    portfolio_data["bubble_size"] = 500

    #
    # Figure layout
    #
    fig = plt.figure(figsize=(20, 14))

    gs = fig.add_gridspec(
        2,
        2,
        width_ratios=[5, 1],
        height_ratios=[4, 1.8],
    )

    ax = fig.add_subplot(gs[0, 0])
    text_ax = fig.add_subplot(gs[0, 1])
    table_ax = fig.add_subplot(gs[1, :])

    text_ax.axis("off")
    table_ax.axis("off")

    #
    # Methodology
    #
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

        r"$\sigma_{BM}$ is always calculated using:"
        "\n"
        "(Sector, Maturity Bucket)\n\n"

        "$\\mathbf{Definitions}$\n"

        r"$R_i$ = Bond Total Return in EUR"
        "\n"

        r"$R_{BM,i}$ = Benchmark Return"
        "\n"

        r"$\sigma_{BM}$ = Benchmark Return"
        "\nStandard Deviation"
        "\n\n"

        "$\\mathbf{Chart}$\n"

        "X-Axis = Portfolio Weight\n"
        "Y-Axis = Adjusted Excess Return"
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
    # Scatter plot
    #
    for category in [
        "Unchanged Position",
        "Primary Market",
        "Initiated",
        "Added",
    ]:

        subset = portfolio_data[
            portfolio_data["position_category"] == category
        ]

        if subset.empty:
            continue

        ax.scatter(
            subset["nav_pct"],
            subset["adj_excess_return"],
            s=subset["bubble_size"],
            color=colors[category],
            alpha=0.7,
            edgecolors="black",
            linewidths=0.5,
            label=category,
        )

    reduce_df = portfolio_data[
        portfolio_data["position_category"] == "Trimmed"
    ]

    if not reduce_df.empty:

        ax.scatter(
            reduce_df["nav_pct"],
            reduce_df["adj_excess_return"],
            s=reduce_df["bubble_size"],
            color="lightgrey",
            alpha=0.7,
            edgecolors="black",
            linewidths=0.5,
            label="Trimmed",
        )

        ax.scatter(
            reduce_df["nav_pct"],
            reduce_df["adj_excess_return"],
            s=reduce_df["bubble_size"],
            facecolors="none",
            edgecolors="red",
            linewidths=1,
        )

    #
    # Reference lines
    #
    ax.axhline(
        0,
        color="black",
        linestyle="--",
        linewidth=1,
    )

    sigma_levels = [-3, -2, -1, 0, 1, 2, 3]

    for level in sigma_levels:
        ax.axhline(
            level,
            color="grey",
            linestyle=":",
            linewidth=1,
            alpha=0.7,
            zorder=0,
        )

    ax.grid(
        alpha=0.3,
        linestyle=":",
    )

    ax.set_yticks(sigma_levels)

    ax.set_yticklabels([
        "-3σ",
        "-2σ",
        "-1σ",
        "0",
        "+1σ",
        "+2σ",
        "+3σ",
    ])

    ax.xaxis.set_major_formatter(
        mtick.PercentFormatter(1.0)
    )

    ax.set_xlabel(
        "% NAV",
        fontsize=14,
    )

    ax.set_ylabel(
        "Adjusted Excess Return (σ)",
        fontsize=14,
    )

    ax.set_title(
        "Bond Adjusted Excess Return vs. Portfolio Weight",
        fontsize=16,
        fontweight="bold",
    )

    ax.tick_params(
        axis="both",
        labelsize=12,
    )

    #
    # Annotate outliers
    #
    outliers = portfolio_data[
        (portfolio_data["adj_excess_return"] <= -2)
        | (portfolio_data["adj_excess_return"] >= 2)
    ]

    for _, row in outliers.iterrows():

        ax.annotate(
            row["instrument_name"],
            (
                row["nav_pct"],
                row["adj_excess_return"],
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            bbox=dict(
                boxstyle="round,pad=0.2",
                fc="white",
                ec="none",
                alpha=0.8,
            ),
        )

    #
    # Legend
    #
    legend_elements = [
        Line2D(
            [0], [0],
            marker="o",
            color="w",
            label="Unchanged Position",
            markerfacecolor="lightgrey",
            markeredgecolor="black",
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker="o",
            color="w",
            label="Primary Market",
            markerfacecolor="tab:green",
            markeredgecolor="black",
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker="o",
            color="w",
            label="Initiated",
            markerfacecolor="tab:blue",
            markeredgecolor="black",
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker="o",
            color="w",
            label="Added",
            markerfacecolor="tab:orange",
            markeredgecolor="black",
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker="o",
            color="w",
            label="Trimmed",
            markerfacecolor="lightgrey",
            markeredgecolor="red",
            markeredgewidth=1,
            markersize=12,
        ),
    ]

    ax.legend(
        handles=legend_elements,
        title="Position Type",
        loc="upper right",
    )

    #
    # Worst performers table
    #
    worst_df = (
        portfolio_data[
            portfolio_data["adj_excess_return"] <= -1.0
        ]
        .copy()
        .sort_values(
            "adj_excess_return",
            ascending=True,
        )
    )

    if not worst_df.empty:

        table_df = worst_df[
            [
                "instrument_name",
                "country",
                "bucket",
                "nav_pct",
                "return",
                "bm_return",
                "excess_return",
                "adj_excess_return",
            ]
        ].copy()

        table_df["nav_pct"] = (
            table_df["nav_pct"].map(lambda x: f"{x:.2%}")
        )

        table_df["return"] = (
            table_df["return"].map(lambda x: f"{x*10000:.1f}bp")
        )

        table_df["bm_return"] = (
            table_df["bm_return"].map(lambda x: f"{x*10000:.1f}bp")
        )

        table_df["excess_return"] = (
            table_df["excess_return"].map(lambda x: f"{x*10000:.1f}bp")
        )

        table_df["adj_excess_return"] = (
            table_df["adj_excess_return"].map(lambda x: f"{x:.2f}σ")
        )

        table_df.columns = [
            "Bond",
            "Country",
            "Bucket",
            "Weight",
            "Return",
            "BM Return",
            "Excess",
            "Adj. Excess Return",
        ]

        table_ax.set_title(
            "Worst Performing Bonds (Adjusted Excess Return ≤ -1σ)",
            fontsize=14,
            fontweight="bold",
            loc="left"
        )

        table = table_ax.table(
            cellText=table_df.values,
            colLabels=table_df.columns,
            loc="center",
            cellLoc="left",
        )

        table.auto_set_font_size(False)
        table.set_fontsize(16)
        table.scale(1, 1.8)

        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(weight="bold")
                cell.set_facecolor("#D9EAD3")

        table.auto_set_column_width(
            col = list(range(len(table_df.columns)))
        )

    plt.subplots_adjust(
        left=0.05,
        right=0.98,
        top=0.95,
        bottom=0.04,
        hspace=0.15,
        wspace=0.05,
    )

    filename = (
        OUTPUT_DIR
        / f"bond_adj_excess_return_"
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
