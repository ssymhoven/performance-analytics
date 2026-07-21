from datetime import datetime
from typing import Tuple

import pandas as pd
import os

from blp import blp
from dotenv import load_dotenv
from analytics.amp import Amp
from analytics.config import CACHE_DIR

load_dotenv()

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
    Retrieve a grouped benchmark return attribution and risk profile from
    Bloomberg BQL and cache the result locally.

    The benchmark is decomposed by:

        - BCLASS Level 1
        - Country of domicile
        - Maturity bucket (floor(workout_years()))

    and provides both return attribution metrics and a historical volatility
    measure at the (BCLASS Level 1, Maturity Bucket) level.

    Parameters
    ----------
    start_date : str
        Start date of the return calculation in YYYY-MM-DD format.

    end_date : str
        End date of the return calculation in YYYY-MM-DD format.

    index : str, default "LEUT1TREU Index"
        Bloomberg benchmark index.

    Returns
    -------
    pandas.DataFrame
        One row per

            (BCLASS L1, Country, Maturity Bucket)

        combination with the following columns:

            id
                Bloomberg-generated group identifier.

            bclass1
                Bloomberg BCLASS level 1 classification.

            country
                Country of domicile.

            bucket
                Maturity bucket defined as

                    floor(workout_years())

            ctr
                Contribution-to-return proxy:

                    weight × return

            weight
                Aggregate benchmark weight of the group.

            return
                Weighted average total return of the group over the
                analysis period.

            std
                Cross-sectional standard deviation of security returns
                within the corresponding

                    (BCLASS Level 1, Maturity Bucket)

                segment.

                The same value is assigned to all countries belonging to
                the same (BCLASS Level 1, Maturity Bucket) combination.

    Caching
    -------
    Results are cached locally as parquet files using

        index
        start_date
        end_date

    as cache keys.

    Subsequent calls with identical parameters load the cached parquet file
    instead of executing Bloomberg requests, reducing API consumption and
    improving runtime.

    Methodology
    -----------
    The main attribution query computes:

        ctr
            Sum(weight × total return)

        weight
            Aggregate benchmark weight

        return
            Weighted average bucket return

    for each:

        (BCLASS Level 1, Country, Maturity Bucket)

    group.

    A second query computes:

        std(group(total_return))

    grouped by:

        (BCLASS Level 1, Maturity Bucket)

    which serves as a simple measure of dispersion/risk within each
    classification and maturity segment.

    The resulting volatility measure is merged onto the attribution output
    using:

        [bclass1, bucket]

    and therefore applies uniformly across all countries within the same
    classification and maturity bucket.

    Notes
    -----
    IMPORTANT: The output is a STATIC-WEIGHTS ATTRIBUTION PROXY and is not
    expected to exactly reconcile to the official benchmark performance
    shown in COMP <GO>.

    Bloomberg Help Desk (H#1330488740) confirmed that:

    * COMP <GO> uses the official index-provider methodology.
    * Official index returns incorporate membership changes, rebalancing,
      weight drift, roll-down effects and daily evolution of the index.
    * BQL queries based on members() operate on a single constituent
      snapshot and therefore represent a bottom-up approximation.

    Consequently:

        sum(ctr)

    may differ from:

        total_return(index)

    over longer horizons.

    To ensure internal consistency, the benchmark universe is fixed using:

        members('<index>', dates=<end_date>)

    so that:

        sum(ctr)

    reconciles to a static-weight benchmark return proxy computed from the
    same constituent set and weights used throughout the attribution.

    Typical Use Case
    ----------------
    The output is intended to support:

        - Portfolio versus benchmark excess return analysis
        - Bucket-level attribution
        - Country allocation analysis
        - Credit sector analysis
        - Relative risk assessment using the std measure
        - Fixed income performance diagnostics
    """

    cache_file = (
        CACHE_DIR / f"{index}_{start_date}_{end_date}.parquet"
    )

    if cache_file.exists():
        return pd.read_parquet(cache_file)

    bquery = blp.BlpQuery(timeout=30000).start()

    query = f"""
        let (
            #bucket = bins(workout_years(), [1,2,3,4,5,6,7,8,9,10,15,20], ['0-1', '1-2', '2-3', '3-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9-10', '10-15', '15-20', '20+']);
            #tr = total_return(calc_interval=range({start_date}, {end_date})) / 100;
            #w  = id().weights / 100;
            #grouped_tr = group(#tr, [classification_name(bclass,1), cntry_of_domicile(), #bucket]);
            #grouped_tr_level = group(#tr, [classification_name(bclass,1), #bucket]);
            #grouped_w  = group(#w,  [classification_name(bclass,1), cntry_of_domicile(), #bucket]);
            #ctr = sum(group(#w * #tr, [classification_name(bclass,1), cntry_of_domicile(), #bucket]));
            #weight = sum(#grouped_w);
            #return = wavg(#grouped_tr, #grouped_w);
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

    std_query = f"""
        let(
            #bucket = bins(workout_years(), [1,2,3,4,5,6,7,8,9,10,15,20], ['0-1', '1-2', '2-3', '3-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9-10', '10-15', '15-20', '20+']);
            #tr = total_return(calc_interval=range({start_date}, {end_date})) / 100;
            #grouped_tr = group(#tr,[classification_name(bclass,1), #bucket]);
            #std = std(#grouped_tr);
        )
        get(#std)
        for(members(['{index}'], dates={end_date}))
    """

    dfs = bquery.bql(std_query)
    std_df = dfs[0]

    std_df = std_df.rename(
        columns={
            "value": "std",
            "CLASSIFICATION_NAME(BCLASS,1)": "bclass1",
            "#BUCKET": "bucket",
        }
    )
    std_df = std_df[["bclass1", "bucket", "std"]]

    result = result.merge(
        std_df,
        on=[
            "bclass1",
            "bucket",
        ],
        how="left",
    )

    if result.isna().any().any():
        print("The DataFrame contains missing values (NaN).")
    else:
        print("The DataFrame does not contain any missing values.")

    result = result.fillna(0)
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
            bins(workout_years(), [1,2,3,4,5,6,7,8,9,10,15,20], ['0-1', '1-2', '2-3', '3-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9-10', '10-15', '15-20', '20+']) as #bucket
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

def build_portfolio(account_segment_id: int, start_date: str, end_date: str, index: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
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

    benchmark_full = benchmark_data[
        ["bclass1", "country", "bucket", "return", "std"]
    ].rename(
        columns={
            "return": "bm_return",
            "std": "bm_std",
        }
    )

    #
    # Primary merge:
    # bclass1 + country + bucket
    #
    portfolio_data = portfolio_data.merge(
        benchmark_full,
        on=["bclass1", "country", "bucket"],
        how="left",
    )

    benchmark_fallback = (
        benchmark_data
        .groupby(
            ["bclass1", "bucket"],
            as_index=False,
        )
        .apply(
            lambda x: pd.Series({
                "bm_return_fb": (
                        (x["return"] * x["weight"]).sum()
                        / x["weight"].sum()
                ),
                "bm_std_fb": x["std"].iloc[0],
            }),
            include_groups=False,
        )
    )

    portfolio_data = portfolio_data.merge(
        benchmark_fallback,
        on=["bclass1", "bucket"],
        how="left",
    )

    #
    # Fill missing benchmark values
    #
    portfolio_data["bm_return"] = (
        portfolio_data["bm_return"]
        .fillna(portfolio_data["bm_return_fb"])
    )

    portfolio_data["bm_std"] = (
        portfolio_data["bm_std"]
        .fillna(portfolio_data["bm_std_fb"])
    )

    portfolio_data["benchmark_match"] = "country"

    mask = portfolio_data["bm_return"].eq(
        portfolio_data["bm_return_fb"]
    )

    portfolio_data.loc[
        mask,
        "benchmark_match"
    ] = "sector_bucket"

    portfolio_data = portfolio_data.drop(
        columns=[
            "bm_return_fb",
            "bm_std_fb",
        ]
    )

    bucket_order = [
        "0-1",
        "1-2",
        "2-3",
        "3-4",
        "4-5",
        "5-6",
        "6-7",
        "7-8",
        "8-9",
        "9-10",
        "10-15",
        "15-20",
        "20+",
    ]

    portfolio_data["bucket"] = pd.Categorical(
        portfolio_data["bucket"],
        categories=bucket_order,
        ordered=True,
    )

    for c in ("first_buy", "latest_buy", "latest_sell", "issue_date"):
        portfolio_data[c] = pd.to_datetime(
            portfolio_data[c],
            errors="coerce",
        )

    return build_attribution(portfolio_data), benchmark_data


def build_attribution(portfolio_data) -> pd.DataFrame:

    portfolio_data = portfolio_data.copy()

    portfolio_data["excess_return"] = (
        portfolio_data["return"] - portfolio_data["bm_return"]
    )

    portfolio_data["adj_excess_return"] = (
        portfolio_data["excess_return"] / portfolio_data["bm_std"]
    )

    portfolio_data["ctr"] = (
        portfolio_data["nav_pct"] * portfolio_data["return"]
    )

    return portfolio_data

def debug_bucket(
    portfolio_data,
    benchmark_data,
    bclass1,
    bucket,
    start_date
):
    print()
    print("=" * 140)
    print(f"{bclass1} | {bucket}")
    print("=" * 140)

    #
    # Benchmark
    #
    bm = benchmark_data[
        (benchmark_data["bclass1"] == bclass1)
        & (benchmark_data["bucket"] == bucket)
    ].copy()

    print("\nBENCHMARK")

    bm["ctr_bp"] = bm["ctr"] * 10000

    print(
        bm[
            [
                "country",
                "weight",
                "return",
                "ctr_bp",
                "std",
            ]
        ]
        .sort_values("weight", ascending=False)
        .to_string(
            index=False,
            formatters={
                "weight": "{:.2%}".format,
                "return": "{:.2%}".format,
                "std": "{:.2%}".format,
                "ctr_bp": "{:.2f}".format,
            },
        )
    )

    print()

    print(
        f"BM Weight: {bm['weight'].sum():.2%}"
    )

    print(
        f"BM Contribution: {bm['ctr_bp'].sum():.2f}bp"
    )

    weighted_std = (
        (bm["weight"] * bm["std"]).sum()
        / bm["weight"].sum()
    )

    print(
        f"Weighted Std: {weighted_std*10000:.2f}bp"
    )

    #
    # Portfolio
    #
    pf = portfolio_data[(portfolio_data["issue_date"] <= datetime.strptime(start_date, "%Y-%m-%d"))].copy()

    pf["nav_pct"] = (
            pf["nav_pct"]
            / pf["nav_pct"].sum()
    )

    pf = pf[
        (pf["bclass1"] == bclass1)
        & (pf["bucket"] == bucket)
    ].copy()

    print()
    print("PORTFOLIO")

    pf["ctr_bp"] = (
        pf["nav_pct"]
        * pf["return"]
        * 10000
    )

    cols = [
        "instrument_name",
        "country",
        "nav_pct",
        "return",
        "bm_return",
        "excess_return",
        "adj_excess_return",
        "ctr_bp"
    ]

    print(
        pf[cols]
        .sort_values(
            "nav_pct",
            ascending=False
        )
        .to_string(
            index=False,
            formatters={
                "nav_pct": "{:.2%}".format,
                "return":
                    lambda x: f"{x*10000:.1f}bp",
                "bm_return":
                    lambda x: f"{x*10000:.1f}bp",
                "excess_return":
                    lambda x: f"{x*10000:.1f}bp",
                "adj_excess_return":
                    lambda x: f"{x:.2f}σ",
                "ctr_bp":
                    lambda x: f"{x:.2f}bp"
            }
        )
    )

    print()

    print(
        f"Portfolio Weight: "
        f"{pf['nav_pct'].sum():.2%}"
    )

    print(
        f"Portfolio Contribution: "
        f"{pf['ctr_bp'].sum():.2f}bp"
    )

    weighted_excess = (
        (pf["nav_pct"] * pf["excess_return"]).sum()
        / pf["nav_pct"].sum()
    )

    print(
        f"Weighted Excess Return: "
        f"{weighted_excess*10000:.2f}bp"
    )