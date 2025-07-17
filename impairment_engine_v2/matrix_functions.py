import math
from typing import Dict, List, Optional, Tuple
from django.db import models
from decimal import Decimal
import json

class IFRS9PDCalculator:
    """
    Implements transition matrix approach for PD calculation
    """

    DEFAULT_PARAMETERS = {
        'max_pd': 0.4999999,  # Maximum PD cap
        'param_60_plus': -3.423051998834600,  # 60+ days parameter
        'param_31_60': -4.523051998834600,  # 31-60 days parameter
        'param_15_30': -3.923051998834600,  # 15-30 days parameter
        'param_8_14': -3.723051998834600,  # 8-14 days parameter
        'param_0_7': -3.523051998834600,  # 0-7 days parameter
        'movement_factors': {
            '60+': -1.84114978814354,
            '31-60': -12.5344652963905,
            '15-30': -7.53446529639056,
            '8-14': -5.33446529639056,
            '0-7': -1.84114978814354
        }
    }

    ARREARS_BUCKETS = ["0-7", "8-14", "15-30", "31-60", "60+"]

    def __init__(self, parameters: Dict = None):
        """Initialize calculator with parameters"""
        self.parameters = parameters or self.DEFAULT_PARAMETERS

    @staticmethod
    def get_arrears_bucket_index(days_past_due: int) -> int:
        """Get the index of arrears bucket for given days past due"""
        if 0 <= days_past_due <= 7:
            return 0  # 0-7
        elif 8 <= days_past_due <= 14:
            return 1  # 8-14
        elif 15 <= days_past_due <= 30:
            return 2  # 15-30
        elif 31 <= days_past_due <= 60:
            return 3  # 31-60
        else:
            return 4  # 60+

    def create_arrears_vector(self, days_past_due: int) -> List[int]:
        """Create binary arrears vector [0,0,0,0,0] with 1 in appropriate bucket"""
        vector = [0] * 5  # Initialize with zeros
        if days_past_due >= 0:
            bucket_index = self.get_arrears_bucket_index(days_past_due)
            vector[bucket_index] = 1
        return vector

    @staticmethod
    def calculate_arrears_movement(current_arrears: List[int],
                                   previous_arrears: List[int]) -> List[int]:
        """Calculate arrears movement vector by subtracting previous from current"""
        if not previous_arrears:
            return current_arrears  # First project - movement equals current

        return [curr - prev for curr, prev in zip(current_arrears, previous_arrears)]

    @staticmethod
    def get_model_pd(loan_data: dict) -> float:
        """
        Get model PD from given loan data
        """
        if "model_pd" in loan_data:
            return float(loan_data["model_pd"])

        # Generate basic model PD based on loan characteristics
        base_pd = 0.02  # 2% base PD

        # Adjust for loan stage
        stage_multipliers = {
            'stage_1': 1.0,
            'stage_2': 2.5,
            'stage_3': 8.0
        }

        stage_multiplier = stage_multipliers.get(loan_data.get('loan_stage', 'stage_1'), 1.0)

        # Adjust for days past due
        days_past_due = loan_data.get('days_past_due', 0)
        if days_past_due > 90:
            dpd_multiplier = 5.0
        elif days_past_due > 60:
            dpd_multiplier = 3.0
        elif days_past_due > 30:
            dpd_multiplier = 2.0
        else:
            dpd_multiplier = 1.0

        # Adjust for sector (simplified)
        sector_multipliers = {
            'Agriculture': 1.5,
            'Mining': 2.0,
            'Manufacturing': 1.2,
            'Professionals': 0.8,
            'Retail': 1.1
        }

        sector_multiplier = sector_multipliers.get(loan_data.get('sector', 'Other'), 1.0)

        model_pd = min(base_pd * stage_multiplier * dpd_multiplier * sector_multiplier, 0.99)

        return model_pd

    def calculate_final_pd(self, model_pd: float, current_arrears: List[int], arrears_movement: List[int]) -> float:
        """
        Calculate final PD from given model and current arrears vector
        """
        # Extract movement values for readability
        movement_60_plus = arrears_movement[4]
        movement_31_60 = arrears_movement[3]
        movement_15_30 = arrears_movement[2]
        movement_8_14 = arrears_movement[1]
        movement_0_7 = arrears_movement[0]

        # Extract current arrears for readability
        current_0_7 = current_arrears[0]
        current_8_14 = current_arrears[1]
        current_15_30 = current_arrears[2]
        current_31_60 = current_arrears[3]
        current_60_plus = current_arrears[4]

        max_pd = self.parameters['max_pd']

        # Excel formula implementation
        if movement_60_plus == 1:
            # Deterioration to 60+ days
            return math.sinh(1 - model_pd) / self.parameters['param_60_plus'] + model_pd

        elif movement_31_60 == 1 and movement_60_plus == 0:
            # Deterioration to 31-60 days (but not 60+)
            return math.sinh(1 - model_pd) / self.parameters['param_60_plus'] + model_pd

        elif movement_60_plus == -1 and sum(current_arrears[0:4]) == 0:
            # Improvement from 60+ to current (no other arrears)
            term1 = model_pd + math.tanh(model_pd) / self.parameters['param_60_plus']
            term2 = math.exp(-1 / math.tanh(model_pd)) if model_pd != 0 else 0
            return min(term1 - term2, max_pd)

        elif movement_60_plus == -1 and current_31_60 == 1:
            # Improvement from 60+ to 31-60 days
            term1 = model_pd + math.tanh(model_pd) / self.parameters['param_31_60']
            term2 = math.exp(-1 / math.tanh(model_pd)) if model_pd != 0 else 0
            return min(term1 - term2, max_pd)

        elif movement_60_plus == -1 and current_15_30 == 1:
            # Improvement from 60+ to 15-30 days
            term1 = model_pd + math.tanh(model_pd) / self.parameters['param_15_30']
            term2 = math.exp(-1 / math.tanh(model_pd)) if model_pd != 0 else 0
            return min(term1 - term2, max_pd)

        elif movement_60_plus == -1 and current_8_14 == 1:
            # Improvement from 60+ to 8-14 days
            term1 = model_pd + math.tanh(model_pd) / self.parameters['param_8_14']
            term2 = math.exp(-1 / math.tanh(model_pd)) if model_pd != 0 else 0
            return min(term1 - term2, max_pd)

        elif movement_60_plus == -1 and current_0_7 == 1:
            # Improvement from 60+ to 0-7 days
            term1 = model_pd + math.tanh(model_pd) / self.parameters['param_0_7']
            term2 = math.exp(-1 / math.tanh(model_pd)) if model_pd != 0 else 0
            return min(term1 - term2, max_pd)

        elif movement_60_plus == 0 and movement_31_60 == 1 and model_pd < 0.5:
            # Deterioration to 31-60 days with low model PD
            result = (math.cosh(1 - model_pd) - 1) / 2.16770203492589 + model_pd
            return min(result, 0.49999)

        elif movement_60_plus == 0 and movement_31_60 == 1:
            # Deterioration to 31-60 days with high model PD
            return (math.cosh(1 - model_pd) - 1) / 2.16770203492589 + model_pd

        elif movement_60_plus == 0 and movement_31_60 == -1:
            # Improvement from 31-60 days
            return math.tanh(model_pd) / self.parameters['movement_factors']['60+'] + model_pd

        elif movement_15_30 == 1:
            # Deterioration to 15-30 days
            return (math.cosh(1 - model_pd) - 1) / 5.39193304696413 + model_pd

        elif movement_15_30 == -1:
            # Improvement from 15-30 days
            return math.tanh(model_pd) / self.parameters['movement_factors']['15-30'] + model_pd

        elif movement_8_14 == 1:
            # Deterioration to 8-14 days
            return (math.cosh(1 - model_pd) - 1) / 10.7680103482031 + model_pd

        elif movement_8_14 == -1:
            # Improvement from 8-14 days
            return math.tanh(model_pd) / self.parameters['movement_factors']['8-14'] + model_pd

        elif movement_0_7 == 1:
            # Deterioration to 0-7 days
            return (math.cosh(1 - model_pd) - 1) / 50.143325434943 + model_pd

        elif movement_0_7 == -1:
            # Improvement from 0-7 days
            return math.tanh(model_pd) / self.parameters['movement_factors']['0-7'] + model_pd

        else:
            # Default case - no significant movement
            return 2 * model_pd - math.sinh(model_pd)


class ProjectPDProcessor:
    """
    Process PD calculations for entire projects
    """
    def __init__(self, calculator: IFRS9PDCalculator = None):
        self.calculator = calculator

    def get_previous_project_arrears(self, current_project, account_number: str) -> Optional[List[int]]:
        """
        Get arrears vector for the same loan from previous project
        """
        previous_projects = current_project.company.projects.filter(
            reporting_date__lt=current_project.reporting_date
        ).order_by('-reporting_date')

        if not previous_projects.exists():
            return None

        previous_project = previous_projects.first()
        previous_loans = previous_project.loan_data

        if not previous_loans:
            return None

        # Find the loan in previous project
        for loan in previous_loans:
            if loan.get('account_number') == account_number:
                days_past_due = loan.get('days_past_due', 0)
                return self.calculator.create_arrears_vector(days_past_due)

        return None

    def calculate_project_pds(self, project) -> Dict:
        """
        Calculate PDs for all loans in the project
        """
        results = {}

        if not project.loan_data:
            return results

        for loan in project.loan_data:
            account_number = loan.get('account_number')
            if not account_number:
                continue

            # Get model PD
            model_pd = self.calculator.get_model_pd(loan)

            # Create current arrears vector
            current_days_past_due = loan.get('days_past_due', 0)
            current_arrears = self.calculator.create_arrears_vector(current_days_past_due)

            # Get previous arrears vector
            previous_arrears = self.get_previous_project_arrears(project, account_number)

            # Calculate arrears movement
            arrears_movement = self.calculator.calculate_arrears_movement(
                current_arrears, previous_arrears
            )

            # Calculate final PD
            final_pd = self.calculator.calculate_final_pd(
                model_pd, current_arrears, arrears_movement
            )

            results[account_number] = {
                'model_pd': model_pd,
                'current_arrears': current_arrears,
                'previous_arrears': previous_arrears,
                'arrears_movement': arrears_movement,
                'final_pd': final_pd,
                'days_past_due': current_days_past_due
            }

        return results

    def update_project_with_pds(self, project) -> None:
        """
        Update project loan_data with calculated PDs
        """
        print("proceeding with project PDs")
        pd_results = self.calculate_project_pds(project)

        # Update loan_data with PD information
        if project.loan_data:
            for loan in project.loan_data:
                account_number = loan.get('account_number')
                if account_number in pd_results:
                    pd_data = pd_results[account_number]
                    loan['model_pd'] = pd_data['model_pd']
                    loan['final_pd'] = pd_data['final_pd']
                    loan['arrears_movement'] = pd_data['arrears_movement']
                    loan['current_arrears'] = pd_data['current_arrears']

        # Save updated project
        project.save()

    def get_pd_grade(self, pd_value: float) -> int:
        if pd_value <= 0.05:
            return 1
        elif pd_value <= 0.1:
            return 2
        elif pd_value <= 0.18:
            return 3
        elif pd_value <= 0.25:
            return 4
        elif pd_value <= 0.3:
            return 5
        elif pd_value <= 0.4:
            return 6
        elif pd_value <= 0.5:
            return 7
        elif pd_value <= 0.6:
            return 8
        elif pd_value <= 0.95:
            return 9
        else:
            return 10

    # def calculate_lifetime_pds(self, project) -> Dict:
    #     """
    #     Calculate PDs for all loans in the project - Original formulas with error handling
    #     """
    #     results = {}
    #
    #     if not project.loan_data:
    #         return results
    #
    #     for loan in project.loan_data:
    #         account_number = loan.get('account_number')
    #         if not account_number:
    #             continue
    #
    #         model_pd = loan.get('model_pd')
    #
    #         # Basic validation
    #         if model_pd is None or model_pd <= 0 or model_pd >= 1:
    #             print(f"Invalid model_pd for account {account_number}: {model_pd}")
    #             continue
    #
    #         try:
    #             # Compute the GR1 Value
    #             pd_grade_1 = self.get_pd_grade(model_pd)
    #
    #             # Compute the Z1, Z2 values
    #             z1 = math.log10(model_pd)
    #             z2 = 0.027657553 + (-0.300785798 * 0.010444444)  # intercept + GDP Growth
    #             z1_z2_sum = z1 + z2
    #
    #             # Compute the expected PD
    #             expected_pd = 1 / (1 + math.exp(-z1_z2_sum))
    #             pd_grade_2 = self.get_pd_grade(expected_pd)
    #
    #             # Compute the PIT value
    #             portfolio_PD = 0.263040845
    #             portfolio_AP = 0.283
    #
    #             pit = ((1 - portfolio_PD) * portfolio_AP * expected_pd) / (
    #                         portfolio_PD * (1 - portfolio_AP) * (1 - expected_pd) + (
    #                             1 - portfolio_PD) * portfolio_AP * expected_pd)
    #
    #             # Generate the lifetime PD
    #             ltpd_yr1 = expected_pd
    #
    #             # Add safe calculation for ltpd_yr2 to handle potential math errors
    #             if ltpd_yr1 > 0:
    #                 try:
    #                     ltpd_yr2 = 1 / (1 + math.exp(math.log10(1 / ltpd_yr1) - 1) - z2)
    #                 except (OverflowError, ZeroDivisionError):
    #                     ltpd_yr2 = 0.0
    #             else:
    #                 ltpd_yr2 = 0.0
    #
    #             # Add safe calculation for ltpd_yr3
    #             if ltpd_yr2 > 0:
    #                 try:
    #                     ltpd_yr3 = 1 / (1 + math.exp(math.log10(1 / ltpd_yr2) - 1) - z2)
    #                 except (OverflowError, ZeroDivisionError):
    #                     ltpd_yr3 = 0.0
    #             else:
    #                 ltpd_yr3 = 0.0
    #
    #             # Add safe calculation for ltpd_yr4
    #             if ltpd_yr3 > 0:
    #                 try:
    #                     ltpd_yr4 = 1 / (1 + math.exp(math.log10(1 / ltpd_yr3) - 1) - z2)
    #                 except (OverflowError, ZeroDivisionError):
    #                     ltpd_yr4 = 0.0
    #             else:
    #                 ltpd_yr4 = 0.0
    #
    #             # Add safe calculation for ltpd_yr5
    #             if ltpd_yr4 > 0:
    #                 try:
    #                     ltpd_yr5 = 1 / (1 + math.exp(math.log10(1 / ltpd_yr4) - 1) - z2)
    #                 except (OverflowError, ZeroDivisionError):
    #                     ltpd_yr5 = 0.0
    #             else:
    #                 ltpd_yr5 = 0.0
    #
    #             # YOUR ORIGINAL LIFETIME PD FORMULAS - UNCHANGED
    #             lifetime_pd_yr1 = ltpd_yr1
    #             lifetime_pd_yr2 = (1 - lifetime_pd_yr1) * ltpd_yr2
    #             lifetime_pd_yr3 = (1 - lifetime_pd_yr2) * ltpd_yr3
    #             lifetime_pd_yr4 = (1 - lifetime_pd_yr3) * ltpd_yr4
    #             lifetime_pd_yr5 = (1 - lifetime_pd_yr4) * ltpd_yr5
    #
    #             # Store the final variables for the loan account
    #             results[account_number] = {
    #                 "expected_pd": expected_pd,
    #                 "lifetime_pd_yr1": lifetime_pd_yr1,
    #                 "lifetime_pd_yr2": lifetime_pd_yr2,
    #                 "lifetime_pd_yr3": lifetime_pd_yr3,
    #                 "lifetime_pd_yr4": lifetime_pd_yr4,
    #                 "lifetime_pd_yr5": lifetime_pd_yr5,
    #                 "ltpd_yr1": ltpd_yr1,
    #                 "ltpd_yr2": ltpd_yr2,
    #                 "ltpd_yr3": ltpd_yr3,
    #                 "ltpd_yr4": ltpd_yr4,
    #                 "ltpd_yr5": ltpd_yr5
    #             }
    #
    #         except Exception as e:
    #             print(f"Error calculating lifetime PDs for account {account_number}: {e}")
    #             print(f"model_pd: {model_pd}")
    #             continue
    #
    #     return results

    def calculate_lifetime_pds(self, project) -> Dict:
        """
        Calculate PDs for all loans in the project
        """
        results = {}

        if not project.loan_data:
            return results

        for loan in project.loan_data:
            account_number = loan.get('account_number')
            if not account_number:
                continue

            model_pd = loan.get('model_pd')

            # Basic validation
            if model_pd is None or model_pd <= 0 or model_pd >= 1:
                print(f"Invalid model_pd for account {account_number}: {model_pd}")
                continue

            try:
                # Compute the GR1 Value
                pd_grade_1 = self.get_pd_grade(model_pd)

                # Compute the Z1, Z2 values
                z1 = math.log10(model_pd)
                z2 = 0.027657553 + (-0.300785798 * 0.010444444)  # intercept + GDP Growth
                z1_z2_sum = z1 + z2

                # Compute the expected PD
                expected_pd = 1 / (1 + math.exp(-z1_z2_sum))
                pd_grade_2 = self.get_pd_grade(expected_pd)

                # Compute the PIT value
                portfolio_PD = 0.263040845
                portfolio_AP = 0.283

                pit = ((1 - portfolio_PD) * portfolio_AP * expected_pd) / (
                        portfolio_PD * (1 - portfolio_AP) * (1 - expected_pd) + (
                        1 - portfolio_PD) * portfolio_AP * expected_pd)

                # Generate the lifetime PD - Year 1 is the expected PD
                ltpd_yr1 = expected_pd

                # Calculate subsequent years' ltpd using proper time decay
                ltpd_values = [ltpd_yr1]

                for year in range(2, 6):  # Years 2-5
                    if ltpd_values[-1] > 0:
                        try:
                            # Apply time decay to previous year's PD
                            time_decay_factor = 0.8  # Adjust this factor based on your model requirements
                            base_pd = ltpd_values[-1] * time_decay_factor

                            # Apply the z2 adjustment (economic cycle adjustment)
                            adjusted_logit = math.log(base_pd / (1 - base_pd)) + z2
                            ltpd_year = 1 / (1 + math.exp(-adjusted_logit))

                            # Ensure PD doesn't become unrealistically low or high
                            ltpd_year = max(0.001, min(0.999, ltpd_year))
                            ltpd_values.append(ltpd_year)

                        except (OverflowError, ZeroDivisionError, ValueError):
                            ltpd_values.append(0.001)  # Minimum PD
                    else:
                        ltpd_values.append(0.001)  # Minimum PD

                # Assign ltpd values
                ltpd_yr1, ltpd_yr2, ltpd_yr3, ltpd_yr4, ltpd_yr5 = ltpd_values

                # Calculate cumulative survival probabilities
                survival_yr1 = 1 - ltpd_yr1
                survival_yr2 = survival_yr1 * (1 - ltpd_yr2)
                survival_yr3 = survival_yr2 * (1 - ltpd_yr3)
                survival_yr4 = survival_yr3 * (1 - ltpd_yr4)
                survival_yr5 = survival_yr4 * (1 - ltpd_yr5)

                # Calculate marginal (lifetime) PDs - probability of default in each specific year
                lifetime_pd_yr1 = ltpd_yr1
                lifetime_pd_yr2 = survival_yr1 * ltpd_yr2
                lifetime_pd_yr3 = survival_yr2 * ltpd_yr3
                lifetime_pd_yr4 = survival_yr3 * ltpd_yr4
                lifetime_pd_yr5 = survival_yr4 * ltpd_yr5

                # Validation: Ensure all lifetime PDs are within reasonable bounds
                lifetime_pds = [lifetime_pd_yr1, lifetime_pd_yr2, lifetime_pd_yr3,
                                lifetime_pd_yr4, lifetime_pd_yr5]

                for i, pd in enumerate(lifetime_pds, 1):
                    if pd < 0 or pd > 1:
                        print(f"Warning: lifetime_pd_yr{i} out of bounds for account {account_number}: {pd}")
                        lifetime_pds[i - 1] = max(0, min(1, pd))

                # Update the corrected values
                lifetime_pd_yr1, lifetime_pd_yr2, lifetime_pd_yr3, lifetime_pd_yr4, lifetime_pd_yr5 = lifetime_pds

                # Store the final variables for the loan account
                results[account_number] = {
                    "expected_pd": expected_pd,
                    "lifetime_pd_yr1": round(lifetime_pd_yr1, 8),
                    "lifetime_pd_yr2": round(lifetime_pd_yr2, 8),
                    "lifetime_pd_yr3": round(lifetime_pd_yr3, 8),
                    "lifetime_pd_yr4": round(lifetime_pd_yr4, 8),
                    "lifetime_pd_yr5": round(lifetime_pd_yr5, 8),
                    "ltpd_yr1": ltpd_yr1,
                    "ltpd_yr2": ltpd_yr2,
                    "ltpd_yr3": ltpd_yr3,
                    "ltpd_yr4": ltpd_yr4,
                    "ltpd_yr5": ltpd_yr5,
                    # Additional useful metrics
                    "survival_yr1": survival_yr1,
                    "survival_yr2": survival_yr2,
                    "survival_yr3": survival_yr3,
                    "survival_yr4": survival_yr4,
                    "survival_yr5": survival_yr5,
                    "cumulative_default_prob": 1 - survival_yr5  # Total default probability over 5 years
                }

            except Exception as e:
                print(f"Error calculating lifetime PDs for account {account_number}: {e}")
                print(f"model_pd: {model_pd}")
                continue

        return results

    def update_project_with_lifetime_pds(self, project) -> None:
        """
        Update project with lifetime PDs
        """
        print("proceeding with lifetime PDs")
        lifetime_pds = self.calculate_lifetime_pds(project)

        print(f"Liftime PDs calculated: {len(lifetime_pds)}")

        # Update the loan data with Lifetime PD information
        if project.loan_data:
            for loan in project.loan_data:
                account_number = loan.get("account_number")
                if account_number in lifetime_pds:
                    pd_data = lifetime_pds[account_number]
                    loan["expected_pd"] = pd_data["expected_pd"]
                    loan["lifetime_pd_yr1"] = pd_data["lifetime_pd_yr1"]
                    loan["lifetime_pd_yr2"] = pd_data["lifetime_pd_yr2"]
                    loan["lifetime_pd_yr3"] = pd_data["lifetime_pd_yr3"]
                    loan["lifetime_pd_yr4"] = pd_data["lifetime_pd_yr4"]
                    loan["lifetime_pd_yr5"] = pd_data["lifetime_pd_yr5"]
                    loan["ltpd_yr1"] = pd_data["ltpd_yr1"]
                    loan["ltpd_yr2"] = pd_data["ltpd_yr2"]
                    loan["ltpd_yr3"] = pd_data["ltpd_yr3"]
                    loan["ltpd_yr4"] = pd_data["ltpd_yr4"]
                    loan["ltpd_yr5"] = pd_data["ltpd_yr5"]

        # Save updated project
        project.save()

