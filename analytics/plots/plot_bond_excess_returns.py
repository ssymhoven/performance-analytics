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
    """
    Plot bond excess return versus portfolio weight.

    Bubble size represents portfolio weight.

    Categories
    ----------
    Primary Market
        Issue date within the analysis period.

    Initiated
        Existing bond where the first purchase occurred during the period.

    Added
        Existing position increased during the period.

    Trimmed
        Position reduced during the period.

    Unchanged Position
        Everything else.
    """

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    portfolio_data = portfolio_data.copy()
    portfolio_data["position_category"] = "Unchanged Position"

    # Primary Market
    mask = portfolio_data["issue_date"].between(start, end)
    portfolio_data.loc[mask, "position_category"] = "Primary Market"

    # Initiated
    mask = (
        ~portfolio_data["issue_date"].between(start, end)
        & portfolio_data["first_buy"].between(start, end)
    )
    portfolio_data.loc[mask, "position_category"] = "Initiated"

    # Added
    mask = (
        ~portfolio_data["issue_date"].between(start, end)
        & (portfolio_data["first_buy"] < start)
        & portfolio_data["latest_buy"].between(start, end)
    )
    portfolio_data.loc[mask, "position_category"] = "Added"

    # Trimmed
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


    fig, ax = plt.subplots(figsize=(14, 10))

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

        # Filled bubble
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

        # Red outer ring
        ax.scatter(
            reduce_df["nav_pct"],
            reduce_df["adj_excess_return"],
            s=reduce_df["bubble_size"],
            facecolors="none",
            edgecolors="red",
            linewidths=1,
        )

    ax.axhline(
        0,
        color="black",
        linestyle="--",
        linewidth=1,
    )

    ax.grid(
        alpha=0.3,
        linestyle=":",
    )

    ax.set_xlabel("% NAV")
    ax.set_ylabel("Excess Return / Bucket Std Dev (σ)")

    ax.set_title(
        f"Bond Adj. Excess Return vs. % NAV\n"
        f"{start_date} to {end_date}"
    )

    ax.xaxis.set_major_formatter(
        mtick.PercentFormatter(1.0)
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

    ax.set_yticks(sigma_levels)

    ax.set_yticklabels([
        "-3σ",
        "-2σ",
        "-1σ",
        "0",
        "+1σ",
        "+2σ",
        "+3σ"
    ])

    legend_elements = [
        Line2D(
            [0], [0],
            marker='o',
            color='w',
            label='Unchanged Position',
            markerfacecolor='lightgrey',
            markeredgecolor='black',
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker='o',
            color='w',
            label='Primary Market',
            markerfacecolor='tab:green',
            markeredgecolor='black',
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker='o',
            color='w',
            label='Initiated',
            markerfacecolor='tab:blue',
            markeredgecolor='black',
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker='o',
            color='w',
            label='Added',
            markerfacecolor='tab:orange',
            markeredgecolor='black',
            markersize=12,
        ),
        Line2D(
            [0], [0],
            marker='o',
            color='w',
            label='Trimmed',
            markerfacecolor='lightgrey',
            markeredgecolor='red',
            markeredgewidth=1,
            markersize=12,
        ),
    ]

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

    ax.legend(
        handles=legend_elements,
        title="Position Type"
    )

    plt.tight_layout()

    filename = (OUTPUT_DIR /
        f"bond_adj_excess_return_"
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