from datetime import datetime
from typing import List, Dict


class ECLCalculator:
    """
    Implements ECL Computations
    """
    def __init__(self):
        self.years = 5

    @staticmethod
    def calculate_present_value(rate: float, nper: int, pmt: float, fv: float = 0, _type: int = 0) -> float:
        # Default fallback for interest rate
        if rate == 0:
            return -(pmt * nper + fv)

        if _type == 1:
            # Payments at the beginning of the period
            pv = (1 + rate) * pmt * (1 - (1 + rate)**(-nper)) / rate - fv / (1 + rate)**nper
        else:
            # Payments at end of the period
            pv = pmt * (1 - (1 + rate) ** (-nper)) / rate - fv / (1 + rate) ** nper
        return -pv

    @staticmethod
    def calculate_future_value(rate: float, nper: int, pmt: float, pv: float = 0, _type: int = 0) -> float:
        if rate == 0:
            return -(pv + pmt * nper)

        if _type == 1:
            # Payments at the beginning of period
            fv = -(pv * (1 + rate) ** nper + pmt * (1 + rate) * ((1 + rate) ** nper - 1) / rate)
        else:
            # Payments at the end of period
            fv = -(pv * (1 + rate) ** nper + pmt * ((1 + rate) ** nper - 1) / rate)

        return fv

    def calculate_outstanding_payments(self, loan_tenor: int, time_elapsed: int) -> List[int]:
        outstanding_payments = []
        remaining_months = max(0, loan_tenor - time_elapsed)

        for year in range(1, self.years + 1):
            if remaining_months <= 0:
                outstanding_payments.append(0)
            elif year == 1:
                # First year: remaining months in current year
                payments = min(12, remaining_months)
                outstanding_payments.append(payments)
                remaining_months -= payments
            else:
                # Subsequent years: 12 months if loan is still active by then
                payments = min(12, remaining_months)
                outstanding_payments.append(payments)
                remaining_months -= payments

        return outstanding_payments

    def calculate_arrears_and_installments(self, arrears_balance: float, eir: float, installment: float, loan_tenor: int, time_elapsed: int) -> List[float]:
        outstanding_payments = self.calculate_outstanding_payments(loan_tenor, time_elapsed)
        arrears_installments = []

        for year in range(self.years):
            payments_this_year = outstanding_payments[year]

            if payments_this_year == 0:
                # No payments remaining
                arrears_installments.append(arrears_balance if year == 0 else 0.0)
            else:
                monthly_rate = eir / 12 if eir > 0 else 0
                present_value = self.calculate_present_value(rate=monthly_rate, nper=payments_this_year, pmt=-installment, fv=0, _type=0)

                # For first year, add arrears balance
                if year == 0:
                    total_value = present_value + arrears_balance
                else:
                    total_value = present_value
                arrears_installments.append(total_value)
        return arrears_installments

    def calculate_monitoring_fees(self, loan_tenor, time_elapsed: int, eir: float, installment: float, loan_amount: float) -> List[float]:
        monitoring_fees = []

        for year in range(1, self.years + 1):
            # Calculate time elapsed at the beginning of each year
            year_time_elapsed = time_elapsed + (year - 1) * 12

            if loan_tenor <= 12:
                # If loan tenor is 12 months or less, no monitoring fees
                fee = 0.0
            elif loan_tenor > 12 and year_time_elapsed > 12:
                # If both conditions are met, no monitoring fees
                fee = 0.0
            elif loan_tenor > 12 and year_time_elapsed <= 12:
                # Calculate monitoring fee using FV function
                monthly_rate = eir / 12 if eir > 0 else 0
                future_value = self.calculate_future_value(
                    rate=monthly_rate,
                    nper=12,
                    pmt=installment,
                    pv=-loan_amount,  # Negative because it's initial principal
                    _type=0
                )
                fee = 0.03 * future_value
            else:
                fee = 0.0
            monitoring_fees.append(fee)
        return monitoring_fees

    def calculate_loan_lifetime_ecl(self,
                           lgd: float,
                           lifetime_pds: List[float],
                           arrears_installments: List[float],
                           monitoring_fees: List[float],
                           eir: float,
                           loan_tenor: int,
                           time_elapsed: int,
                           residual_value: float = 0.0) -> List[float]:
        """
        Calculates ECL for the 5-year period
        """
        if len(lifetime_pds) != self.years:
            raise ValueError(f"Lifetime PDs array must have {self.years} elements.")
        if len(arrears_installments) != self.years:
            raise ValueError(f"Arrears installments array must have {self.years} elements.")
        if len(monitoring_fees) != self.years:
            raise ValueError(f"Monitoring fees array must have {self.years} elements.")

        ecl_values = []

        for year in range(self.years):
            # Calculate remaining periods for this year
            remaining_months = max(0, loan_tenor - time_elapsed - (year * 12))
            remaining_years = remaining_months / 12

            if remaining_years <= 0:
                ecl_values.append(0.0)
                continue

            # Calculate the present value component
            present_value = self.calculate_present_value(
                rate=eir,
                nper=remaining_months,
                pmt=0,
                fv=-residual_value, # Negative because it's a future value
                _type=0
            )

            # ECL Computation: LGD * PD * (Arrears_Installments + Monitoring_Fees + Present Value)
            exposure = (arrears_installments[year] + monitoring_fees[year] + present_value)

            ecl = lgd * lifetime_pds[year] * exposure
            ecl_values.append(max(0.0, round(ecl, 2)))

        return ecl_values

    def calculate_loan_ecl(self, loan_data: dict) -> dict:
        """
        Calculate Loan ECL
        """
        # Extract loan parameters with fallbacks for your data structure
        arrears_balance = loan_data.get("arrears_amount", loan_data.get("arrears_balance", 0.0))
        eir = loan_data.get("interest_rate", 0.0) / 100 if loan_data.get("interest_rate", 0.0) > 1 else loan_data.get(
            "interest_rate", 0.0)
        installment = loan_data.get("installment_amount", 0.0)
        loan_tenor = loan_data.get("loan_tenor", 0)
        loan_amount = loan_data.get("loan_amount", 0.0)
        lgd = loan_data.get("computed_lgd",  0.45)

        # Calculate the time elapsed on a loan
        time_elapsed = 0
        if "opening_date" in loan_data and "maturity_date" in loan_data:
            try:
                # Format the Opening Date
                if isinstance(loan_data["opening_date"], str):
                    opening_date = datetime.strptime(loan_data["opening_date"], "%Y-%m-%d").date()
                else:
                    opening_date = loan_data["opening_date"]

                # Format the Maturity Date
                if isinstance(loan_data["maturity_date"], str):
                    maturity_date = datetime.strptime(loan_data["maturity_date"], "%Y-%m-%d").date()
                else:
                    maturity_date = loan_data["maturity_date"]

                today = datetime.today()

                # Calculate elapsed time
                months_since_opening = ((today.year - opening_date.year) * 12 + (today.month - opening_date.month))
                time_elapsed = max(0, months_since_opening)

            except (ValueError, TypeError):
                # Fallback Implementation: use days_past_due to estimate the time elapsed
                days_past_due = loan_data.get("days_past_due", 0)
                # Rough estimate: if loan is past due, it's likely near or past maturity
                if days_past_due > 0:
                    time_elapsed = loan_tenor  # Assume full tenor elapsed if past due

        # Get the PDs from loan data
        lifetime_pds = [
            loan_data.get("ltpd_yr1", 0.0),
            loan_data.get("ltpd_yr2", 0.0),
            loan_data.get("ltpd_yr3", 0.0),
            loan_data.get("ltpd_yr4", 0.0),
            loan_data.get("ltpd_yr5", 0.0),
        ]

        # Calculate outstanding payments
        outstanding_payments = self.calculate_outstanding_payments(loan_tenor, time_elapsed)

        # Calculate arrears and installments array
        arrears_installments = self.calculate_arrears_and_installments(arrears_balance, eir, installment, loan_tenor, time_elapsed)

        # Calculate monitoring fees
        monitoring_fees = self.calculate_monitoring_fees(loan_tenor, time_elapsed, eir, installment, loan_amount)

        # Calculate ECL
        loan_ecl_values = self.calculate_loan_lifetime_ecl(lgd, lifetime_pds, arrears_installments, monitoring_fees, eir, loan_tenor, time_elapsed)

        # Calculate total ECL
        total_ecl = sum(loan_ecl_values)

        # Calculate total ECL
        return {
            "outstanding_payments": outstanding_payments,
            "arrears_installments": [round(x, 2) for x in arrears_installments],
            "monitoring_fees": [round(x, 2) for x in monitoring_fees],
            "ecl_values": [round(x, 2) for x in loan_ecl_values],
            "loan_ecl": total_ecl,
            "total_ecl": total_ecl,
            "lgd": lgd,
            "loan_tenor": loan_tenor,
            "time_elapsed": time_elapsed,
            "eir": eir,
            "arrears_balance": arrears_balance,
        }


class ProjectECLProcessor:
    """
    Process ECL calculations for the project
    """
    def __init__(self, ecl_calculator: ECLCalculator = None):
        self.ecl_calculator  = ecl_calculator or ECLCalculator()

    def calculate_project_ecls(self, project) -> Dict:
        """
        Calculates ECLs for all loans in the project
        """
        results = {}

        if not project.loan_data:
            return results

        for loan in project.loan_data:
            account_number = loan.get("account_number")
            if not account_number:
                continue

            try:
                ecl_result = self.ecl_calculator.calculate_loan_ecl(loan)
                results[account_number] = ecl_result
            except Exception as e:
                print(f"Error calculating ECL for account {account_number}: {str(e)}")
                continue

        return results

    def update_project_with_ecls(self, project) -> None:
        """
        Updates ECLs for all loans in the project
        """
        print("Proceeding with ECL calculations")
        ecl_results = self.calculate_project_ecls(project)

        print(f"ECL calculations completed: {len(ecl_results)} against {len(project.loan_data)} loans.")

        # Update loan data with ECL information
        if project.loan_data:
            for loan in project.loan_data:
                account_number = loan.get("account_number")
                if account_number in ecl_results:
                    ecl_data = ecl_results[account_number]

                    # Update loan with ECL Components
                    loan["outstanding_payments"] = ecl_data["outstanding_payments"]
                    loan["arrears_installments"] = ecl_data["arrears_installments"]
                    loan["monitoring_fees"] = ecl_data["monitoring_fees"]
                    loan["ecl_values"] = ecl_data["ecl_values"]
                    loan["total_ecl"] = ecl_data["total_ecl"]

        # Save the updated project
        project.save()
        print(f"Project updated with ECL Calculations.")
