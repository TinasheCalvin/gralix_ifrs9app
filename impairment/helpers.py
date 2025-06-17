from django.shortcuts import get_object_or_404
from .models import PDCalculationResult, Project
import pandas as pd


def run_calculations_for_project(project_id, new_data):
    project = get_object_or_404(Project, id=project_id)
    
    try:
        calculation_result = PDCalculationResult.objects.get(project=project)
        calculation_result.base_transition_matrix = new_data.get('base_transition_matrix')
        calculation_result.stage_1_cumulative = new_data.get('stage_1_cumulative')
        calculation_result.stage_2_cumulative = new_data.get('stage_2_cumulative')
        calculation_result.stage_1_marginal = new_data.get('stage_1_marginal')
        calculation_result.stage_2_marginal = new_data.get('stage_2_marginal')
        calculation_result.cures = new_data.get('cures')
        calculation_result.recoveries = new_data.get('recoveries')
        calculation_result.save()

    except PDCalculationResult.DoesNotExist:
        PDCalculationResult.objects.create(
            project=project,
            base_transition_matrix=new_data.get('base_transition_matrix'),
            stage_1_cumulative=new_data.get('stage_1_cumulative'),
            stage_2_cumulative=new_data.get('stage_2_cumulative'),
            stage_1_marginal=new_data.get('stage_1_marginal'),
            stage_2_marginal=new_data.get('stage_2_marginal'),
            cures=new_data.get('cures'),
            recoveries=new_data.get('recoveries'),
        )


def remove_loan_duplicates(dataframe:pd.DataFrame):
    # Assuming loan_data is already loaded as a DataFrame
    grouped_data = dataframe.groupby('account_no').agg({
        'report_date': 'first',
        'client_id': 'first',
        'disbursement_date': 'first',
        'maturity_date': 'first',
        'loan_type': 'first',
        'disbursed_amount': 'first',
        'outstanding_balance': 'sum',  # Sum the outstanding balance for duplicate account numbers
        'interest_rate': 'first',
        'days_past_due': 'first',
        'staging': 'first',
        'frequency': 'first',
        'building': 'first',
        'land': 'first',
        'bond': 'first',
        'motor_vehicle': 'first',
        'cash': 'first',
        'equity': 'first',
        'other': 'first'
    }).reset_index()

    return grouped_data
