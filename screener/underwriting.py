"""Cash-flow underwriting + multi-year equity build projection."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class UnderwritingParams:
    down_pct: float            # e.g. 0.25
    rate: float                # annual mortgage rate, e.g. 0.07
    term_years: int            # e.g. 30
    closing_pct: float         # closing costs as % of price, e.g. 0.02
    tax_pct: float             # annual property tax as % of price, e.g. 0.022
    insurance_pct: float       # annual insurance as % of price, e.g. 0.005
    vacancy_pct: float         # e.g. 0.05
    maintenance_pct: float     # % of effective gross rent, e.g. 0.08
    mgmt_pct: float            # % of effective gross rent, e.g. 0.08
    appreciation_pct: float    # annual appreciation, e.g. 0.03
    rent_growth_pct: float     # annual rent growth, e.g. 0.02


def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    if principal <= 0:
        return 0.0
    n = years * 12
    if annual_rate == 0:
        return principal / n
    r = annual_rate / 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def underwrite_row(price: float, monthly_rent: float, p: UnderwritingParams) -> dict:
    """Year-1 underwriting for a single listing."""
    if not np.isfinite(price) or price <= 0 or not np.isfinite(monthly_rent) or monthly_rent <= 0:
        return {
            "cap_rate": np.nan, "coc": np.nan, "noi": np.nan,
            "annual_cash_flow": np.nan, "monthly_cash_flow": np.nan,
            "monthly_pi": np.nan, "cash_invested": np.nan,
            "annual_opex": np.nan, "annual_rent": np.nan,
        }

    down = price * p.down_pct
    loan = price - down
    closing = price * p.closing_pct
    cash_invested = down + closing

    annual_rent = monthly_rent * 12
    effective_rent = annual_rent * (1 - p.vacancy_pct)

    tax = price * p.tax_pct
    insurance = price * p.insurance_pct
    maintenance = effective_rent * p.maintenance_pct
    mgmt = effective_rent * p.mgmt_pct
    opex = tax + insurance + maintenance + mgmt

    noi = effective_rent - opex
    pi = monthly_payment(loan, p.rate, p.term_years)
    annual_debt = pi * 12

    annual_cf = noi - annual_debt
    cap_rate = noi / price
    coc = annual_cf / cash_invested if cash_invested > 0 else np.nan

    return {
        "cap_rate": cap_rate,
        "coc": coc,
        "noi": noi,
        "annual_cash_flow": annual_cf,
        "monthly_cash_flow": annual_cf / 12,
        "monthly_pi": pi,
        "cash_invested": cash_invested,
        "annual_opex": opex,
        "annual_rent": annual_rent,
    }


def underwrite(df: pd.DataFrame, p: UnderwritingParams) -> pd.DataFrame:
    results = df.apply(
        lambda r: underwrite_row(r.get("price", np.nan), r.get("monthly_rent", np.nan), p),
        axis=1,
        result_type="expand",
    )
    return pd.concat([df.reset_index(drop=True), results.reset_index(drop=True)], axis=1)


def equity_projection(price: float, monthly_rent: float, p: UnderwritingParams, years: int = 10) -> pd.DataFrame:
    """Year-by-year equity, cash flow, and total return for a single listing."""
    if not np.isfinite(price) or price <= 0:
        return pd.DataFrame()

    down = price * p.down_pct
    loan = price - down
    closing = price * p.closing_pct
    cash_invested = down + closing
    r = p.rate / 12
    n_total = p.term_years * 12
    pi_monthly = monthly_payment(loan, p.rate, p.term_years)

    rows = []
    balance = loan
    cumulative_cf = 0.0

    for year in range(1, years + 1):
        # Amortize 12 months
        for _ in range(12):
            if balance <= 0:
                break
            interest = balance * r
            principal_pay = max(pi_monthly - interest, 0)
            balance = max(balance - principal_pay, 0)

        # This year's rent & opex (apply growth)
        gross_rent = monthly_rent * 12 * (1 + p.rent_growth_pct) ** (year - 1)
        effective_rent = gross_rent * (1 - p.vacancy_pct)
        opex = (
            price * p.tax_pct
            + price * p.insurance_pct
            + effective_rent * (p.maintenance_pct + p.mgmt_pct)
        )
        noi = effective_rent - opex
        annual_cf = noi - pi_monthly * 12
        cumulative_cf += annual_cf

        value = price * (1 + p.appreciation_pct) ** year
        equity = value - balance
        total_return = equity + cumulative_cf - cash_invested

        rows.append({
            "year": year,
            "property_value": value,
            "loan_balance": balance,
            "equity": equity,
            "annual_cash_flow": annual_cf,
            "cumulative_cash_flow": cumulative_cf,
            "total_return": total_return,
        })

    return pd.DataFrame(rows)
