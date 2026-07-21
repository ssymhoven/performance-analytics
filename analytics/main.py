from datetime import datetime

import pandas as pd

from analytics.plots.plot_bond_excess_returns import plot_bond_excess_return
from analytics.plots.plot_attribution_heatmap import plot_attribution_heatmap
from analytics.plots.plot_selection_heatmap import plot_selection_heatmap
from analytics.portfolio import build_portfolio, debug_bucket


def print_portfolio_statistics(
    portfolio_data: pd.DataFrame,
):
    df = portfolio_data.copy()

    print()
    print("=" * 170)
    print("PORTFOLIO ATTRIBUTION SUMMARY")
    print("=" * 170)
    print(f"Portfolio Return:        {df['ctr'].sum()*100:.2f}%")
    print(f"Average Excess Return:   {df['excess_return'].mean()*10000:.1f} bp")
    print(f"Median Excess Return:    {df['excess_return'].median()*10000:.1f} bp")
    print(f"Average Adj. Excess:     {df['adj_excess_return'].mean():.2f} σ")
    print(f"Median Adj. Excess:      {df['adj_excess_return'].median():.2f} σ")
    print(f"Positive Alpha Names:    {(df['excess_return'] >= 0).sum()}")
    print(f"Negative Alpha Names:    {(df['excess_return'] < 0).sum()}")
    print(f"Portfolio Bonds:         {len(df)}")
    print("=" * 170)

def print_underperformers(
    portfolio_data: pd.DataFrame,
    start_date: str
):
    df = portfolio_data.copy()

    under = (
        df[
            (df["adj_excess_return"] <= -1) & (df["issue_date"] <= datetime.strptime(start_date, "%Y-%m-%d"))
        ]
        .sort_values(
            "adj_excess_return"
        )
    )

    print()
    print("=" * 170)
    print("SIGNIFICANT UNDERPERFORMERS (WITHOUT NEW ISSUES)")
    print("=" * 170)

    if under.empty:
        print("No positions found.")
        return

    for _, row in under.iterrows():

        print(
            f"{row['instrument_name'][:40]:40}"
            f" | % NAV={row['nav_pct']:6.2%}"
            f" | Return={row['return']:7.2%}"
            f" | Return BM={row['bm_return']:7.2%}"
            f" | Excess={row['excess_return']*10000:7.1f}bp"
            f" | Std={row['adj_excess_return']:6.2f}σ"
            f" | {row['bclass1']:18} "
            f" | {row['country']}"
        )

    print("=" * 170)

if __name__ == "__main__":
    account_segment_id = 79939970
    start_date = "2026-06-01"
    end_date = "2026-07-17"
    index = "LBEATREU Index"
    prefix = f"{account_segment_id}_{start_date}_{end_date}"

    portfolio_data, benchmark_data = build_portfolio(
        index=index,
        account_segment_id=account_segment_id,
        start_date=start_date,
        end_date=end_date
    )

    plot_bond_excess_return(
        portfolio_data=portfolio_data,
        account_segment_id=account_segment_id,
        start_date=start_date,
        end_date=end_date,
    )

    plot_attribution_heatmap(
        portfolio_data=portfolio_data,
        benchmark_data=benchmark_data,
        account_segment_id=account_segment_id,
        start_date=start_date,
        end_date=end_date,
    )

    plot_selection_heatmap(
        portfolio_data=portfolio_data,
        account_segment_id=account_segment_id,
        start_date=start_date,
        end_date=end_date
    )

    print_portfolio_statistics(portfolio_data=portfolio_data)
    print_underperformers(portfolio_data=portfolio_data, start_date=start_date)

    debug_bucket(
        portfolio_data,
        benchmark_data,
        "Securitized",
        "5-6",
        start_date
    )