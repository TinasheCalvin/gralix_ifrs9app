import math
import random
from decimal import Decimal
import pandas as pd
from scipy.stats import norm
from impairment_engine_v2.models import OLSCoefficient, LGDRiskFactor, LGDRiskFactorValue


def prepare_loan_data(project):
    """ Convert loan data JSON into a DataFrame. """
    return pd.DataFrame(project.loan_data)


# def enrich_loan_data(df):
#     """ Adds LGD Specific columns to loan data. """
#     df["client_type"] = df["loan_type"].map({
#         "Personal Loan": "Individual",
#         "Staff Loan": "Individual",
#         "SSB Loans": "Individual",
#     }).fillna("Corporate")
#
#     df["collateral_type"] = df["loan_type"].map({
#         "Corporate Working Capital Loan": "Machinery",
#         "Micro Lease Loan": "Vehicle",
#     }).fillna("Other")
#
#     return df

def enrich_loan_data(df, company):
    """
    Adds LGD Specific columns to loan data with randomized collateral types.

    Args:
        df: DataFrame containing loan data
        company: Company instance to fetch available collateral types

    Returns:
        Enriched DataFrame with client_type and randomized collateral_type
    """
    # Set client types (same as before)
    df["client_type"] = df["loan_type"].map({
        "Personal Loan": "Individual",
        "Staff Loan": "Individual",
        "SSB Loans": "Individual",
    }).fillna("Corporate")

    # Get available collateral types from the company's risk factors
    try:
        collateral_factor = LGDRiskFactor.objects.get(
            company=company,
            accessor_key="collateral_type"
        )
        collateral_options = list(collateral_factor.values.filter(is_active=True).values_list('name', flat=True))

        if not collateral_options:
            collateral_options = ["Real Estate", "Vehicle", "Machinery", "Inventory", "Other"]

    except LGDRiskFactor.DoesNotExist:
        collateral_options = ["Real Estate", "Vehicle", "Machinery", "Inventory", "Other"]

    # Randomly assign collateral types
    df["collateral_type"] = [random.choice(collateral_options) for _ in range(len(df))]

    return df


def save_enriched_loan_data(project, df):
    """ Stores enriched loan data. """
    project.loan_data = df.to_dict(orient='records')
    project.save()


def enrich_project_loan_data(project):
    df = prepare_loan_data(project)
    df = enrich_loan_data(df, project.company)
    save_enriched_loan_data(project, df)
    return df


def compute_cumulative_loan_gd(company, loan_data):
    """
    Calculate LGD using logistic regression from selected factor values + tenor + GDP
    """
    gdp_value = company.gdp_value or Decimal("0.010444444")
    gdp_coeff = company.gdp_coefficient or Decimal("0.01")
    intercept = Decimal("-1.454126971")
    base_score = intercept

    # Get all active risk factors for this company
    risk_factors = company.risk_factors.filter(is_active=True)

    for factor in risk_factors:
        # Get the loan value using the accessor key
        loan_value = loan_data.get(factor.accessor_key)
        if not loan_value:
            continue

        try:
            # Find matching factor value
            value = factor.values.get(
                name__iexact=loan_value.strip(),
                is_active=True
            )

            # Get coefficient
            coeff = OLSCoefficient.objects.filter(
                factor_value=value,
                company=company
            ).first()

            if coeff:
                base_score += (value.identifier * coeff.coefficient)

        except LGDRiskFactorValue.DoesNotExist:
            continue

    # Add tenor contribution (if you want to make this dynamic too)
    tenor_coeff = OLSCoefficient.objects.filter(
        company=company,
        is_tenor=True
    ).first()

    if tenor_coeff:
        tenor = Decimal(loan_data.get("loan_tenor", 0))
        base_score += (tenor * tenor_coeff.coefficient)

    # GDP contribution
    base_score += gdp_value * gdp_coeff

    # # Logistic transform
    # try:
    #     lgd = 1 - (1 / (1 + math.exp(-float(base_score))))
    #     # return min(max(lgd, company.default_lgd_floor / 100), company.default_lgd_ceiling / 100)
    #     return lgd
    # except (ZeroDivisionError, OverflowError):
    #     return company.default_lgd_floor / 100

    # Normal Distribution Implementation
    try:
        mu = 0.1525  # 15.25%
        sigma = 1.1243  # 112.43%
        # Calculate cumulative probability
        probability = norm.cdf(float(base_score), float(mu), float(sigma))

        return round(probability, 6)
    except (ZeroDivisionError, OverflowError):
        return company.default_lgd_floor / 100


def compute_final_lgd(cumulative_gd, count, p_lgd_1=0.5, p_lgd_0=0.5):
    """
    Compute the final LGD based on cumulative GD
    """
    ols_nb = cumulative_gd / count
    return round((1 - p_lgd_0) * (p_lgd_1 + (1 - p_lgd_0) * ols_nb), 9)
