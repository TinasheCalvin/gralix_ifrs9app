import math
from decimal import Decimal
import pandas as pd
from impairment_engine_v2.models import OLSCoefficient, LGDRiskFactor, LGDRiskFactorValue


def prepare_loan_data(project):
    """ Convert loan data JSON into a DataFrame. """
    return pd.DataFrame(project.loan_data)


def enrich_loan_data(df):
    """ Adds LGD Specific columns to loan data. """
    df["client_type"] = df["loan_type"].map({
        "Personal Loan": "Individual",
        "Staff Loan": "Individual",
        "SSB Loans": "Individual",
    }).fillna("Corporate")

    df["collateral_type"] = df["loan_type"].map({
        "Corporate Working Capital Loan": "Machinery",
        "Micro Lease Loan": "Vehicle",
    }).fillna("Other")

    return df


def save_enriched_loan_data(project, df):
    """ Stores enriched loan data. """
    project.loan_data = df.to_dict(orient='records')
    project.save()


def enrich_project_loan_data(project):
    df = prepare_loan_data(project)
    df = enrich_loan_data(df)
    save_enriched_loan_data(project, df)
    return df

def compute_lgd_from_ols(company, loan_data):
    """
    Calculate LGD using logistic regression from selected factor values + tenor + GDP
    """

    # Pull GDP and coefficient
    gdp_value = company.gdp_value or Decimal("3.00")
    gdp_coeff = company.gdp_coefficient or Decimal("0.05")
    intercept = Decimal("0.00")  # optional: make this configurable later

    base_score = intercept

    # Map loan fields to factor values
    factor_mapping = {
        'Client Type': loan_data.get("client_type"),
        'Collateral Type': loan_data.get("collateral_type"),
        'Asset Type': loan_data.get("loan_type")
    }

    # Match to factor values
    for factor_name, loan_value in factor_mapping.items():
        try:
            factor = LGDRiskFactor.objects.get(name__iexact=factor_name, company=company)
            value = factor.values.get(name__iexact=loan_value.strip())
            coeff = OLSCoefficient.objects.filter(factor_value=value, company=company).first()
            if coeff:
                base_score += coeff.coefficient
        except LGDRiskFactor.DoesNotExist:
            continue
        except LGDRiskFactorValue.DoesNotExist:
            continue

    tenor = Decimal(loan_data.get("loan_tenor", 0))
    # Update the base score
    base_score += (tenor * 0) # Assuming tenor coefficient is 0

    # GDP contribution
    base_score += gdp_value * gdp_coeff

    # Logistic transform
    try:
        lgd = 1 / (1 + math.exp(-float(base_score)))
        return lgd
    except ZeroDivisionError:
        return base_score
    except OverflowError:
        return Decimal(1)