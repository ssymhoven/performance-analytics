import os
from pathlib import Path

import numpy as np
import pandas as pd
from blp import blp
from dotenv import load_dotenv
from matplotlib.lines import Line2D
from analytics.amp import Amp
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

load_dotenv()
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def get_portfolio(account_segment_id: int):
    amp = Amp(
        client_id=os.getenv("AMP_CLIENT_ID"),
        client_secret=os.getenv("AMP_CLIENT_SECRET")
    )

    resp = amp.get_portfolio_by_id(account_segment_id=account_segment_id)

    node = (((resp or {}).get("data") or {}).get("portfolio") or {})
    items = node.get("portfolioPositions") or []

    rows = []

    for p in items:

        buy_dates = []
        sell_dates = []

        for position in p.get("positions") or []:
            for accounting in position.get("accountings") or []:

                if accounting.get("orderAction") == "BUY_OPEN":
                    ts = accounting.get("accountingDate")

                    if ts is not None:
                        buy_dates.append(ts)

                if accounting.get("orderAction") == "SELL_CLOSE":
                    ts = accounting.get("accountingDate")

                    if ts is not None:
                        sell_dates.append(ts)

        first_buy = min(buy_dates) if buy_dates else None
        latest_buy = max(buy_dates) if buy_dates else None
        latest_sell = max(sell_dates) if sell_dates else None

        rows.append({
            "position_type": p.get("positionType"),
            "instrument_name": ((p.get("rateable") or {}).get("name")),
            "isin": (((p.get("rateable") or {}).get("symbol") or {}).get("identifier")),
            "asset_class": ((p.get("rateable") or {}).get("assetClassLiteral")),
            "nav_pct": (
                (((p.get("percentNAV") or {}).get("value") or {}).get("quantity")) / 100
            ),
            "issue_date": ((p.get("rateable") or {}).get("dateOfIssue")),
            "first_buy": (
                pd.to_datetime(first_buy, unit="ms")
                if first_buy is not None else pd.NaT
            ),
            "latest_buy": (
                pd.to_datetime(latest_buy, unit="ms")
                if latest_buy is not None else pd.NaT
            ),
            "latest_sell": (
                pd.to_datetime(latest_sell, unit="ms")
                if latest_sell is not None else pd.NaT
            ),
        })

    df = pd.DataFrame(rows)
    df = df[df["asset_class"] == "BOND"].copy()

    return df

def get_benchmark_data(start_date: str, end_date: str, index: str = "LEUT1TREU Index") -> pd.DataFrame:
    """
    Retrieve a grouped benchmark return attribution from Bloomberg BQL and
    cache the result locally.

    The attribution is grouped by:

        - BCLASS Level 1
        - Country of domicile
        - Maturity bucket (floor(workout_years()))

    and returns:

        - ctr: contribution-to-return proxy
        - weight: aggregated benchmark weight
        - return: weighted-average bucket return

    Parameters
    ----------
    start_date : str
        Start date of the return calculation in YYYY-MM-DD format.

    end_date : str
        End date of the return calculation in YYYY-MM-DD format.

    index : str, default "LEU1TREU Index"
        Bloomberg benchmark index.

    Returns
    -------
    pandas.DataFrame
        One row per

            (BCLASS L1, Country, Maturity Bucket)

        combination with the following columns:

            ID
            CLASSIFICATION_NAME(BCLASS,1)
            CNTRY_OF_DOMICILE()
            #BUCKET
            ctr
            weight
            return

        where

            ctr     = Sum(weight × total return)
            weight  = Aggregate benchmark weight
            return  = Weighted-average bucket return

    Caching
    -------
    Results are cached locally as parquet files using

        benchmark
        start_date
        end_date

    as cache keys.

    Subsequent calls with identical parameters will load the parquet file
    instead of consuming Bloomberg API requests.

    Notes
    -----
    IMPORTANT: The output is a STATIC-WEIGHTS ATTRIBUTION PROXY and is
    not expected to exactly match the official index-level return shown in
    COMP <GO>.

    * COMP <GO> uses the official index methodology.
    * The index return is calculated using daily membership evolution,
      rebalancing, weight drift, bond roll-down and constituent changes.
    * A BQL query based on members() uses a single constituent snapshot
      and therefore represents a bottom-up attribution approximation.

    Consequently:

        sum(ctr)

    may differ slightly from

        total_return(index)

    over longer periods.

    To ensure internal consistency, the query uses:

        members('<benchmark>', dates=<end_date>)

    so that:

        sum(ctr)

    reconciles to a static-weight index return proxy calculated from
    the same constituent snapshot and weight set.

    """

    cache_file = (
        CACHE_DIR / f"{index}_{start_date}_{end_date}.parquet"
    )

    if cache_file.exists():
        return pd.read_parquet(cache_file)

    bquery = blp.BlpQuery(timeout=30000).start()

    query = f"""
        let(
            #bucket = floor(workout_years());

            #ctr =
                sum(
                    group(
                        id().weights / 100 *
                        total_return(
                            calc_interval=range({start_date}, {end_date})
                        ) / 100,
                        [
                            classification_name(bclass,1),
                            cntry_of_domicile(),
                            #bucket
                        ]
                    )
                );

            #weight =
                sum(
                    group(
                        id().weights / 100,
                        [
                            classification_name(bclass,1),
                            cntry_of_domicile(),
                            #bucket
                        ]
                    )
                );

            #return =
                wavg(
                    group(
                        total_return(
                            calc_interval=range({start_date}, {end_date})
                        ) / 100,
                        [
                            classification_name(bclass,1),
                            cntry_of_domicile(),
                            #bucket
                        ]
                    ),
                    group(
                        id().weights / 100,
                        [
                            classification_name(bclass,1),
                            cntry_of_domicile(),
                            #bucket
                        ]
                    )
                );
        )

        get(#ctr, #weight, #return)
        for(members(['{index}'], dates={end_date}))
    """

    dfs = bquery.bql(query)

    ctr_df, weight_df, return_df = dfs

    ctr_df = ctr_df.rename(columns={"value": "ctr"})
    weight_df = weight_df.rename(columns={"value": "weight"})
    return_df = return_df.rename(columns={"value": "return"})

    keys = [
        "id",
        "CLASSIFICATION_NAME(BCLASS,1)",
        "CNTRY_OF_DOMICILE()",
        "#BUCKET",
    ]

    result = (
        ctr_df[keys + ["ctr"]]
        .merge(
            weight_df[keys + ["weight"]],
            on=keys,
            how="outer",
        )
        .merge(
            return_df[keys + ["return"]],
            on=keys,
            how="outer",
        )
    )

    result = result.rename(columns={
        "CLASSIFICATION_NAME(BCLASS,1)": "bclass1",
        "CNTRY_OF_DOMICILE()": "country",
        "#BUCKET": "bucket",
    })

    result.to_parquet(cache_file, index=False)

    return result

def get_portfolio_data(
    account_segment_id: int,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Retrieve portfolio holdings from AMP and enrich them with Bloomberg data.

    Parameters
    ----------
    account_segment_id : int
        AMP account segment identifier.

    start_date : str
        Start date in YYYY-MM-DD format.

    end_date : str
        End date in YYYY-MM-DD format.

    Returns
    -------
    pd.DataFrame

        Portfolio positions enriched with:

            return
            bclass1
            country
            bucket

    Caching
    -------
    Data is cached locally and restored if the same parameter
    combination is requested again.
    """

    cache_file = (
        CACHE_DIR
        / f"portfolio_{account_segment_id}_{start_date}_{end_date}.parquet"
    )

    if cache_file.exists():
        return pd.read_parquet(cache_file)

    portfolio = get_portfolio(account_segment_id)

    if portfolio.empty:
        return portfolio

    isins = (
        portfolio["isin"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not isins:
        return portfolio

    bquery = blp.BlpQuery(timeout=30000).start()

    isin_list = ", ".join(f"'{isin}'" for isin in isins)

    query = f"""
        get(
            total_return(
                calc_interval=range({start_date}, {end_date})
            ) / 100 as #return,

            classification_name(
                classification_scheme=BCLASS,
                classification_level='1'
            ) as #bclass1,

            cntry_of_domicile() as #country,

            floor(workout_years()) as #bucket
        )

        for([{isin_list}])
    """

    dfs = bquery.bql(query)

    return_df, bclass_df, country_df, bucket_df = dfs

    return_df = return_df.rename(
        columns={
            "id": "isin",
            "value": "return",
        }
    )

    bclass_df = bclass_df.rename(
        columns={
            "id": "isin",
            "value": "bclass1",
        }
    )

    country_df = country_df.rename(
        columns={
            "id": "isin",
            "value": "country",
        }
    )

    bucket_df = bucket_df.rename(
        columns={
            "id": "isin",
            "value": "bucket",
        }
    )

    bloomberg_data = (
        return_df[["isin", "return"]]
        .merge(
            bclass_df[["isin", "bclass1"]],
            on="isin",
            how="outer",
        )
        .merge(
            country_df[["isin", "country"]],
            on="isin",
            how="outer",
        )
        .merge(
            bucket_df[["isin", "bucket"]],
            on="isin",
            how="outer",
        )
    )

    result = portfolio.merge(
        bloomberg_data,
        on="isin",
        how="left",
    )

    result.to_parquet(cache_file, index=False)

    return result


def plot_bond_excess_return(
    portfolio_data: pd.DataFrame,
    account_segment_id: int,
    start_date: str,
    end_date: str,
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

    for c in ("first_buy", "latest_buy", "latest_sell", "issue_date"):
        portfolio_data[c] = pd.to_datetime(
            portfolio_data[c],
            errors="coerce",
        )
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
            subset["excess_return"],
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
            reduce_df["excess_return"],
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
            reduce_df["excess_return"],
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

    ax.set_xlabel("Portfolio Weight")
    ax.set_ylabel("Excess Return")

    ax.set_title(
        f"Bond Excess Return vs Portfolio Weight\n"
        f"{start_date} to {end_date}"
    )

    ax.xaxis.set_major_formatter(
        mtick.PercentFormatter(1.0)
    )

    ax.yaxis.set_major_formatter(
        mtick.PercentFormatter(1.0)
    )

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

    ax.legend(
        handles=legend_elements,
        title="Position Type",
        frameon=True,
    )

    plt.tight_layout()

    filename = (
        f"bond_excess_return_"
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

    print(f"Saved plot: {filename}")

if __name__ == "__main__":
    account_segment_id = 1595635
    start_date = "2026-06-01"
    end_date = "2026-07-16"
    index = "LEU1TREU Index"

    portfolio_data = get_portfolio_data(
        account_segment_id=account_segment_id,
        start_date=start_date,
        end_date=end_date,
    )

    benchmark_data = get_benchmark_data(
        start_date=start_date,
        end_date=end_date,
        index=index,
    )

    portfolio_data = portfolio_data.merge(
        benchmark_data[
            ["bclass1", "country", "bucket", "return"]
        ].rename(
            columns={"return": "bm_return"}
        ),
        on=["bclass1", "country", "bucket"],
        how="left",
    )

    portfolio_data["excess_return"] = (
        portfolio_data["return"]
        - portfolio_data["bm_return"]
    )

    plot_bond_excess_return(
        portfolio_data=portfolio_data,
        account_segment_id=account_segment_id,
        start_date=start_date,
        end_date=end_date,
    )