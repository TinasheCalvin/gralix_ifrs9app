import base64
import csv
import io
from io import BytesIO
import pandas as pd
import numpy as np

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import (
    CompanyForm, ProjectForm, BranchMappingForm, BranchMappingBulkForm,
    CBLParametersForm, DataUploadForm, CompanyParametersUpdateForm
)
from .models import (
    Company, Project, BranchMapping, CBLParameters
)

import logging
logger = logging.getLogger(__name__)


def is_superuser(user):
    return user.is_superuser


@login_required
def home(request):
    """Home page showing companies based on user permissions"""
    if request.user.is_authenticated:
        if request.user.is_superuser:
            company_list = Company.objects.all().order_by('name')
        else:
            company_list = Company.objects.filter(created_by=request.user).order_by('name')

        paginator = Paginator(company_list, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'impairment_engine/home.html', {'page_obj': page_obj})
    else:
        return redirect('sign_in')


@login_required
def create_company(request):
    """Create a new company with default IFRS9 and CBL parameters"""
    if request.method == 'POST':
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.created_by = request.user
            company.save()
            messages.success(request, "Company Added Successfully!")
            return HttpResponseRedirect(reverse('index'))
    else:
        form = CompanyForm()
    return render(request, 'impairment_engine/create_company.html', {'form': form})


@login_required
def company_detail(request, company_slug):
    """Company detail view showing overview and quick stats"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to access this company.")
        return redirect('home')

    # Get company statistics
    projects = company.projects.all()
    active_projects = projects.filter(status__in=['setup', 'data_upload', 'processing', 'validation'])
    completed_projects = projects.filter(status='completed')
    branch_mappings = company.branch_mappings.filter(is_active=True)

    context = {
        'company': company,
        'projects': projects[:5],  # Show latest 5 projects
        'active_projects_count': active_projects.count(),
        'completed_projects_count': completed_projects.count(),
        'branch_mappings_count': branch_mappings.count(),
        'total_projects': projects.count(),
    }

    return render(request, 'impairment/company_detail.html', context)


@login_required
def company_projects(request, company_slug):
    """List all projects for a company"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to access this company.")
        return redirect('home')

    projects_list = company.projects.all().order_by('-created_at')
    paginator = Paginator(projects_list, 15)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'company': company,
        'page_obj': page_obj,
    }

    return render(request, 'impairment_engine/company_projects.html', context)


@login_required
def create_project(request, company_slug):
    """Create a new project within a company"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to create projects for this company.")
        return redirect('index')

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.company = company
            project.created_by = request.user
            project.save()
            messages.success(request, "Project Created Successfully!")
            return HttpResponseRedirect(reverse('company_projects', args=[company_slug]))
    else:
        form = ProjectForm()

    return render(request, 'impairment_engine/create_project.html', {'company': company, 'form': form})


@login_required
def project_detail(request, company_slug, project_slug):
    """Project detail view showing status and progress"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to access this project.")
        return redirect('home')

    # Get project statistics
    recent_uploads = project.data_uploads.all().order_by('-uploaded_at')[:5]
    cbl_parameters = project.cbl_parameters.all().order_by('loan_type', 'currency')

    context = {
        'company': company,
        'project': project,
        'recent_uploads': recent_uploads,
        'cbl_parameters': cbl_parameters,
        'total_uploads': project.data_uploads.count(),
        'total_parameters': cbl_parameters.count(),
    }

    return render(request, 'impairment/project_detail.html', context)


@login_required
def data_upload_wizard(request, company_slug, project_slug):
    # Fetch company and project details
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to view this project dashboard.")
        return redirect('home')

    # Check if data upload not already processed
    if project.loan_report_uploaded and project.arrears_report_uploaded and project.status != "":
        messages.error(request, "Project data has already been uploaded. Navigating to project dashboard.")
        return redirect('index')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        print(f"INFO: Excel file received: {excel_file}")
        print(f"INFO: Excel file name: {excel_file.name if excel_file else 'None'}")

        if not excel_file:
            print(f"ERROR: No excel file provided")
            messages.error(request, "Please select an excel file for upload.")
            return render(request, 'impairment_engine/data_upload_wizard.html', {
                'company_slug': company_slug,
                'project_slug': project_slug,
                'company': company,  # Added this
                'project': project,  # Added this
                'step': 1
            })

        try:
            print(f"INFO: Attempting to read Excel file")
            # Reset file pointer to beginning
            excel_file.seek(0)
            xlsx = pd.ExcelFile(excel_file)
            print(f"INFO: Excel file loaded successfully")
            print(f"INFO: Sheet names: {xlsx.sheet_names}")

            # Read file content and encode as base64 for session storage
            excel_file.seek(0)  # Reset file pointer again
            file_content = excel_file.read()
            file_content_b64 = base64.b64encode(file_content).decode('utf-8')

            # Store data in session
            request.session['upload_data'] = {
                'file_name': excel_file.name,
                'sheet_names': xlsx.sheet_names,
                'file_content_b64': file_content_b64  # Store as base64 string
            }
            request.session.modified = True
            return redirect('process_sheets', company_slug=company_slug, project_slug=project_slug)

        except Exception as e:
            import traceback
            messages.error(request, f"Error reading excel file: {str(e)}")
            return render(request, 'impairment_engine/data_upload_wizard.html', {
                'company_slug': company_slug,
                'project_slug': project_slug,
                'company': company,
                'project': project,
                'step': 1
            })

    return render(request, 'impairment_engine/data_upload_wizard.html', {
        'company_slug': company_slug,
        'project_slug': project_slug,
        'company': company,  # Added this
        'project': project,  # Added this
        'step': 1
    })


@login_required
def process_sheet_selection(request, company_slug, project_slug):
    print(f"DEBUG: process_sheet_selection called")
    print(f"DEBUG: Request method: {request.method}")
    print(f"DEBUG: Session keys: {list(request.session.keys())}")
    print(f"DEBUG: upload_data in session: {'upload_data' in request.session}")

    if 'upload_data' in request.session:
        print(f"DEBUG: upload_data contents: {list(request.session['upload_data'].keys())}")

    if 'upload_data' not in request.session:
        print(f"DEBUG: No upload_data in session, redirecting to upload_wizard")
        messages.error(request, "Please select an excel file for upload.")
        return redirect('upload_wizard', company_slug=company_slug, project_slug=project_slug)

    if request.method == 'POST':
        loan_sheet = request.POST.get('loan_sheet')
        arrears_sheet = request.POST.get('arrears_sheet')
        print(f"DEBUG: POST data - loan_sheet: {loan_sheet}, arrears_sheet: {arrears_sheet}")

        if not loan_sheet or not arrears_sheet:
            messages.error(request, "Please select both loan and arrears sheets")
            return render(request, 'impairment_engine/data_upload_wizard.html', {
                'company_slug': company_slug,
                'project_slug': project_slug,
                'sheet_names': request.session['upload_data']['sheet_names'],
                'step': 2
            })

        # Store sheet selections in session
        request.session['upload_data'].update({
            'loan_sheet': loan_sheet,
            'arrears_sheet': arrears_sheet
        })
        request.session.modified = True
        print(f"DEBUG: Updated session with sheet selections")

        return redirect('process_mapping', company_slug=company_slug, project_slug=project_slug)

    print(f"DEBUG: Rendering step 2 template")
    print(f"DEBUG: Available sheet names: {request.session['upload_data']['sheet_names']}")
    return render(request, 'impairment_engine/data_upload_wizard.html', {
        'company_slug': company_slug,
        'project_slug': project_slug,
        'sheet_names': request.session['upload_data']['sheet_names'],
        'step': 2
    })


@login_required
def process_column_mapping(request, company_slug, project_slug):
    print(f"DEBUG: process_column_mapping called")
    ARREARS_BUCKETS = [
        ('00-07 DAYS', '0_7_days', 0, 7),
        ('08-14 DAYS', '8_14_days', 8, 14),
        ('15-30 DAYS', '15_30_days', 15, 30),
        ('31-60 DAYS', '31_60_days', 31, 60),
        ('61-90 DAYS', '61_90_days', 61, 90),
        ('91-120 DAYS', '91_120_days', 91, 120),
        ('121-150 DAYS', '121_150_days', 121, 150),
        ('151-180 DAYS', '151_180_days', 151, 180),
        ('181-360 DAYS', '181_360_days', 181, 360),
        ('OVER 360 DAYS', 'over_360_days', 361, 999999)
    ]

    if 'upload_data' not in request.session or 'loan_sheet' not in request.session['upload_data']:
        print(f"DEBUG: Missing session data, redirecting to upload_wizard")
        messages.error(request, "Please complete previous steps first")
        return redirect('upload_wizard', company_slug=company_slug, project_slug=project_slug)

    try:
        # Decode the base64 file content
        file_content_b64 = request.session['upload_data']['file_content_b64']
        file_content = base64.b64decode(file_content_b64.encode('utf-8'))
        xls = pd.ExcelFile(BytesIO(file_content))

        loan_df = pd.read_excel(xls, sheet_name=request.session['upload_data']['loan_sheet'], nrows=1)
        arrears_df = pd.read_excel(xls, sheet_name=request.session['upload_data']['arrears_sheet'], nrows=1)

        loan_columns = loan_df.columns.tolist()
        arrears_columns = arrears_df.columns.tolist()
        print(f"DEBUG: Loan columns: {loan_columns}")
        print(f"DEBUG: Arrears columns: {arrears_columns}")

        # Check if bucket columns are present in arrears data
        bucket_columns_found = []
        for bucket_name, _, _, _ in ARREARS_BUCKETS:
            if bucket_name in arrears_columns:
                bucket_columns_found.append(bucket_name)

        bucket_columns_present = len(bucket_columns_found) > 0
        request.session['upload_data']['has_bucket_columns'] = bucket_columns_present
        request.session['upload_data']['bucket_columns_found'] = bucket_columns_found

        print(f"DEBUG: Bucket columns found: {bucket_columns_found}")
        print(f"DEBUG: Has bucket columns: {bucket_columns_present}")

        request.session.modified = True

    except Exception as e:
        print(f"DEBUG: Error reading Excel sheets: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        messages.error(request, f"Error reading Excel sheets: {str(e)}")
        return redirect('upload_wizard', company_slug=company_slug, project_slug=project_slug)

    # Define field mappings with descriptions
    loan_field_config = [
        ('account_number', 'Account Number', True),
        ('branch', 'Branch', True),
        ('client_name', 'Client Name', True),
        ('loan_type', 'Loan Type', True),
        ('opening_date', 'Opening Date', True),
        ('maturity_date', 'Maturity Date', True),
        ('currency', 'Currency', True),
        ('loan_amount', 'Loan Amount', True),
        ('installment_amount', 'Installment Amount', True),
        ('capital_balance', 'Capital Balance', True),
        ('interest_rate', 'Interest Rate', True),
        ('loan_tenor', 'Loan Tenor (Days)', False),  # Can be computed
        ('days_to_maturity', 'Days to Maturity', False),  # Can be computed
    ]

    # Conditional arrears field config based on bucket presence
    if bucket_columns_present:
        arrears_field_config = [
            ('account_number', 'Account Number', True),
            ('currency', 'Currency', False),  # Optional since might come from loan sheet
            ('capital_balance', 'Capital Balance', False),  # Optional since might come from loan sheet
        ]
    else:
        arrears_field_config = [
            ('account_number', 'Account Number', True),
            ('currency', 'Currency', True),
            ('capital_balance', 'Capital Balance', True),
            ('arrears_amount', 'Arrears Amount', True),
            ('exposure', 'Exposure Amount', False),  # Can be computed
            ('days_past_due', 'Days Past Due', True),
        ]

    if request.method == 'POST':
        print(f"DEBUG: Processing column mapping POST request")
        # Process the mappings
        mappings = {
            'loan_mappings': {},
            'arrears_mappings': {},
        }

        # Process loan mappings
        for field_name, description, is_required in loan_field_config:
            selected_column = request.POST.get(f'loan_{field_name}')
            if selected_column:
                mappings['loan_mappings'][field_name] = selected_column

        # Process arrears mappings
        for field_name, description, is_required in arrears_field_config:
            selected_column = request.POST.get(f'arrears_{field_name}')
            if selected_column:
                mappings['arrears_mappings'][field_name] = selected_column

        print(f"DEBUG: Mappings created: {mappings}")

        # Store mappings in session
        request.session['upload_data']['mappings'] = mappings
        request.session.modified = True
        return redirect('finalize_upload', company_slug=company_slug, project_slug=project_slug)

    return render(request, 'impairment_engine/data_upload_wizard.html', {
        'company_slug': company_slug,
        'project_slug': project_slug,
        'loan_columns': loan_columns,
        'arrears_columns': arrears_columns,
        'loan_field_config': loan_field_config,
        'arrears_field_config': arrears_field_config,
        'step': 3,
        'ARREARS_BUCKETS': ARREARS_BUCKETS,
        'has_bucket_columns': bucket_columns_present,
        'bucket_columns_found': bucket_columns_found,
    })


@login_required
def finalize_data_upload_v2(request, company_slug, project_slug):
    print(f"DEBUG: Finalize_data_upload called")
    if 'upload_data' not in request.session or 'mappings' not in request.session['upload_data']:
        print(f"DEBUG: Missing session data for finalize")
        messages.error(request, "Please complete all steps first")
        return redirect('upload_wizard', company_slug=company_slug, project_slug=project_slug)

    try:
        project = Project.objects.get(slug=project_slug, company__slug=company_slug)
        company = Company.objects.get(slug=company_slug)
        upload_data = request.session['upload_data']

        # Temporarily define rate for USD
        rate = 13.7031

        # Add this check at the start of finalize_data_upload_v2
        print(
            f"DEBUG: Company Stage Thresholds - Stage 1: {company.stage_1_threshold_days}, Stage 2: {company.stage_2_threshold_days}")

        # Decode the base64 file content
        file_content_b64 = upload_data['file_content_b64']
        file_content = base64.b64decode(file_content_b64.encode('utf-8'))
        xls = pd.ExcelFile(BytesIO(file_content))

        # Update status to data upload processing
        project.status = 'processing'

        # Process loan data
        print(f"DEBUG: Processing loan data")
        loan_df = pd.read_excel(xls, sheet_name=upload_data['loan_sheet'])
        print(f"Loans columns currently {loan_df.columns}")

        # Invert the mapping to go from source_column -> target_column
        loan_mapping_inverted = {v: k for k, v in upload_data['mappings']['loan_mappings'].items()}
        print(f"DEBUG: Loan mapping inverted: {loan_mapping_inverted}")
        loan_df = loan_df.rename(columns=loan_mapping_inverted)

        # Keep only mapped columns for loan data
        loan_mapped_columns = list(loan_mapping_inverted.values())
        loan_df = loan_df[loan_mapped_columns]
        print(f"Loans columns after filtering: {loan_df.columns}")

        # Process arrears data
        print(f"DEBUG: Processing arrears data")
        arrears_df = pd.read_excel(xls, sheet_name=upload_data['arrears_sheet'])
        print(f"Arrears columns currently {arrears_df.columns}")

        # Define arrears buckets at module level for consistency
        ARREARS_BUCKETS = [
            ('00-07 DAYS', '0_7_days', 0, 7),
            ('08-14 DAYS', '8_14_days', 8, 14),
            ('15-30 DAYS', '15_30_days', 15, 30),
            ('31-60 DAYS', '31_60_days', 31, 60),
            ('61-90 DAYS', '61_90_days', 61, 90),
            ('91-120 DAYS', '91_120_days', 91, 120),
            ('121-150 DAYS', '121_150_days', 121, 150),
            ('151-180 DAYS', '151_180_days', 151, 180),
            ('181-360 DAYS', '181_360_days', 181, 360),
            ('OVER 360 DAYS', 'over_360_days', 361, 999999)
        ]

        # Process bucket-based arrears if bucket columns are present
        if upload_data.get('has_bucket_columns', False):
            print(f"DEBUG: Processing bucket-based arrears data")

            # Initialize arrears columns
            arrears_df['arrears_amount'] = 0.0
            arrears_df['days_past_due'] = 0

            # Process each row to find which bucket has the arrears amount
            for idx, row in arrears_df.iterrows():
                total_arrears = 0.0
                max_dpd = 0  # Track the highest DPD bucket with arrears

                for bucket_name, field_name, min_days, max_days in ARREARS_BUCKETS:
                    bucket_value = 0.0

                    # Check if this exact bucket column exists and has a value
                    if bucket_name in arrears_df.columns:
                        cell_value = row[bucket_name]

                        # Handle different representations of empty/zero values
                        if pd.isna(cell_value) or cell_value == '-' or cell_value == '' or cell_value == 0:
                            bucket_value = 0.0
                        else:
                            try:
                                # Handle string numbers with commas
                                if isinstance(cell_value, str):
                                    cell_value = cell_value.replace(',', '').replace(' ', '')
                                bucket_value = float(cell_value)
                            except (ValueError, TypeError):
                                bucket_value = 0.0

                        if bucket_value > 0:
                            total_arrears += (bucket_value / rate) # Divide by the rate for accurate USD Reporting
                            # Set DPD to the MAXIMUM days in the bucket (this was the bug!)
                            # For staging purposes, we want to use max_days to be conservative
                            max_dpd = max(max_dpd, max_days)

                arrears_df.at[idx, 'arrears_amount'] = round(total_arrears, 2)
                arrears_df.at[idx, 'days_past_due'] = max_dpd

                # Debug print for the specific account
                if row.get('account_number') == 'LD2308905320':  # Your example account
                    print(
                        f"DEBUG: Account {row.get('account_number')} - Total arrears: {total_arrears}, Max DPD: {max_dpd}")

            print(
                f"DEBUG: Processed {len(arrears_df[arrears_df['arrears_amount'] > 0])} accounts with arrears from bucket format")

            # Invert the mapping for arrears (only for account_number and other mapped fields)
            arrears_mapping_inverted = {v: k for k, v in upload_data['mappings']['arrears_mappings'].items()}
            print(f"DEBUG: Arrears mapping inverted: {arrears_mapping_inverted}")

            # Rename only the mapped columns
            arrears_df = arrears_df.rename(columns=arrears_mapping_inverted)

            # Keep mapped columns plus our computed ones
            arrears_mapped_columns = list(arrears_mapping_inverted.values()) + ['arrears_amount', 'days_past_due']
            # Filter to only columns that exist
            arrears_mapped_columns = [col for col in arrears_mapped_columns if col in arrears_df.columns]
            arrears_df = arrears_df[arrears_mapped_columns]

        else:
            # Traditional processing for non-bucket data
            print(f"DEBUG: Processing traditional arrears data")
            arrears_mapping_inverted = {v: k for k, v in upload_data['mappings']['arrears_mappings'].items()}
            print(f"DEBUG: Arrears mapping inverted: {arrears_mapping_inverted}")
            arrears_df = arrears_df.rename(columns=arrears_mapping_inverted)

            # Keep only mapped columns for arrears data
            arrears_mapped_columns = list(arrears_mapping_inverted.values())
            arrears_df = arrears_df[arrears_mapped_columns]

        print(f"Arrears columns after filtering: {arrears_df.columns}")

        # Verify the account_number column exists before merging
        print(f"DEBUG: 'account_number' in loan_df: {'account_number' in loan_df.columns}")
        print(f"DEBUG: 'account_number' in arrears_df: {'account_number' in arrears_df.columns}")

        # Merge loan and arrears data on account_number
        print(f"DEBUG: Merging loan and arrears data")
        merged_df = loan_df.merge(
            arrears_df,
            on='account_number',
            how='left',  # Keep all loans, even those without arrears
            suffixes=('', '_arrears')
        )

        # Handle missing arrears data, set defaults for accounts not in arrears
        merged_df['days_past_due'] = merged_df['days_past_due'].fillna(0)
        merged_df['arrears_amount'] = merged_df['arrears_amount'].fillna(0)

        # Handle capital balance conflicts (prioritize loan data)
        if 'capital_balance_arrears' in merged_df.columns:
            merged_df['capital_balance'] = merged_df['capital_balance'].fillna(merged_df['capital_balance_arrears'])
            merged_df = merged_df.drop('capital_balance_arrears', axis=1)

        # Handle currency conflicts (prioritize loan data)
        if 'currency_arrears' in merged_df.columns:
            merged_df['currency'] = merged_df['currency'].fillna(merged_df['currency_arrears'])
            merged_df = merged_df.drop('currency_arrears', axis=1)

        """ Calculate computed fields """
        print(f"DEBUG: Calculating computed fields")

        # Calculate exposure
        merged_df["exposure"] = merged_df['capital_balance'] + merged_df['arrears_amount']

        # Calculate loan_tenor in months if dates are available
        if 'opening_date' in merged_df.columns and 'maturity_date' in merged_df.columns:
            merged_df['opening_date'] = pd.to_datetime(merged_df['opening_date'], errors='coerce')
            merged_df['maturity_date'] = pd.to_datetime(merged_df['maturity_date'], errors='coerce')
            # Calculate loan tenor in months (approximate using 30.44 days per month)
            loan_tenor_days = (merged_df['maturity_date'] - merged_df['opening_date']).dt.days
            merged_df['loan_tenor'] = (loan_tenor_days / 30.44).round().astype('Int64')  # Round to nearest month

        # Calculate days_to_maturity (set to 0 if past maturity date)
        if 'maturity_date' in merged_df.columns:
            today = pd.Timestamp.now().normalize()
            days_to_maturity = (merged_df['maturity_date'] - today).dt.days
            merged_df['days_to_maturity'] = days_to_maturity.where(days_to_maturity >= 0, 0)

        # Add loan stage based on days past due - FIXED LOGIC
        def get_loan_stage(dpd):
            print(f"DEBUG: Calculating stage for DPD: {dpd} (type: {type(dpd)})")
            if pd.isna(dpd) or dpd == 0:
                return '' # Leave Loan Stage null for loans not in arrears
            elif dpd <= company.stage_1_threshold_days:
                return 'stage_1'
            elif dpd <= company.stage_2_threshold_days:
                return 'stage_2'
            else:
                return 'stage_3'

        merged_df['loan_stage'] = merged_df['days_past_due'].apply(get_loan_stage)

        # Debug: Print some examples
        print(f"DEBUG: Sample DPD and stages:")
        for idx, row in merged_df.head(10).iterrows():
            print(
                f"  Account: {row.get('account_number', 'N/A')}, DPD: {row['days_past_due']}, Stage: {row['loan_stage']}")

        # Define the expected final columns
        expected_columns = [
            'account_number', 'branch', 'client_name', 'loan_type', 'opening_date',
            'maturity_date', 'currency', 'loan_amount', 'capital_balance', 'interest_rate',
            'arrears_amount', 'days_past_due', 'exposure', 'loan_tenor',
            'days_to_maturity', 'loan_stage'
        ]

        # Filter to only keep expected columns that exist in the dataframe
        final_columns = [col for col in expected_columns if col in merged_df.columns]
        merged_df = merged_df[final_columns]

        # Ensure all columns are JSON serializable
        for col in merged_df.columns:
            if pd.api.types.is_numeric_dtype(merged_df[col]):
                merged_df[col] = merged_df[col].apply(lambda x: float(x) if pd.notnull(x) else 0)
            elif pd.api.types.is_datetime64_any_dtype(merged_df[col]):
                merged_df[col] = merged_df[col].dt.strftime('%Y-%m-%d')
            elif merged_df[col].dtype == 'object':
                merged_df[col] = merged_df[col].astype(str)

        # Convert to dictionary format and store
        loan_data = merged_df.to_dict(orient='records')

        # Store the merged data
        project.status = 'completed'
        project.loan_data = loan_data
        project.loan_report_uploaded = True
        project.arrears_report_uploaded = True

        # Add metadata about the upload
        project.upload_metadata = {
            'total_accounts': len(loan_data),
            'accounts_with_arrears': len(merged_df[merged_df['days_past_due'] > 0]),
            'accounts_current': len(merged_df[merged_df['days_past_due'] == 0]),
            'upload_date': pd.Timestamp.now().isoformat(),
            'total_exposure': float(merged_df['exposure'].sum()),
            'total_arrears': float(merged_df['arrears_amount'].sum()),
            'status_breakdown': merged_df['loan_stage'].value_counts().to_dict(),
            'processing_type': 'bucket_based' if upload_data.get('has_bucket_columns', False) else 'traditional'
        }

        project.save()

        # Clear session data
        if 'upload_data' in request.session:
            del request.session['upload_data']

        messages.success(request, f"Data uploaded successfully! Processed {len(loan_data)} loan accounts.")
        return redirect('project_dashboard', company_slug=company_slug, project_slug=project_slug)

    except Exception as e:
        print(f"DEBUG: Error in finalize_data_upload: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        messages.error(request, f"Error processing data: {str(e)}")
        return redirect('upload_wizard', company_slug=company_slug, project_slug=project_slug)


@login_required
def manage_branch_mappings(request, company_slug):
    """Manage branch mappings for a company"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to manage branch mappings.")
        return redirect('home')

    branch_mappings = company.branch_mappings.all().order_by('branch_name')

    context = {
        'company': company,
        'branch_mappings': branch_mappings,
    }

    return render(request, 'impairment/manage_branch_mappings.html', context)


@login_required
def add_branch_mapping(request, company_slug):
    """Add individual branch mapping"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to add branch mappings.")
        return redirect('home')

    if request.method == 'POST':
        form = BranchMappingForm(request.POST)
        if form.is_valid():
            branch_mapping = form.save(commit=False)
            branch_mapping.company = company
            branch_mapping.save()
            messages.success(request, "Branch mapping added successfully!")
            return HttpResponseRedirect(reverse('manage_branch_mappings', args=[company_slug]))
    else:
        form = BranchMappingForm()

    context = {
        'company': company,
        'form': form,
    }

    return render(request, 'impairment/add_branch_mapping.html', context)


@login_required
def bulk_upload_branch_mappings(request, company_slug):
    """Bulk upload branch mappings via CSV"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to upload branch mappings.")
        return redirect('home')

    if request.method == 'POST':
        form = BranchMappingBulkForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            try:
                # Read CSV file
                file_data = csv_file.read().decode('utf-8')
                csv_data = csv.DictReader(io.StringIO(file_data))

                created_count = 0
                error_count = 0
                errors = []

                with transaction.atomic():
                    for row_num, row in enumerate(csv_data, start=2):
                        try:
                            branch_name = row.get('branch_name', '').strip()
                            branch_code = row.get('branch_code', '').strip()
                            is_active = row.get('is_active', 'true').strip().lower() in ['true', '1', 'yes', 'y']

                            if not branch_name or not branch_code:
                                errors.append(f"Row {row_num}: Branch name and code are required")
                                error_count += 1
                                continue

                            # Check if branch code already exists
                            if BranchMapping.objects.filter(company=company, branch_code=branch_code).exists():
                                errors.append(f"Row {row_num}: Branch code '{branch_code}' already exists")
                                error_count += 1
                                continue

                            BranchMapping.objects.create(
                                company=company,
                                branch_name=branch_name,
                                branch_code=branch_code,
                                is_active=is_active
                            )
                            created_count += 1

                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                            error_count += 1

                if created_count > 0:
                    messages.success(request, f"Successfully created {created_count} branch mappings.")

                if error_count > 0:
                    messages.warning(request, f"{error_count} rows had errors. See details below.")
                    for error in errors[:10]:  # Show first 10 errors
                        messages.error(request, error)

                return HttpResponseRedirect(reverse('manage_branch_mappings', args=[company_slug]))

            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
    else:
        form = BranchMappingBulkForm()

    context = {
        'company': company,
        'form': form,
    }

    return render(request, 'impairment/bulk_upload_branch_mappings.html', context)


@login_required
def edit_branch_mapping(request, company_slug, mapping_id):
    """Edit individual branch mapping"""
    company = get_object_or_404(Company, slug=company_slug)
    branch_mapping = get_object_or_404(BranchMapping, id=mapping_id, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to edit branch mappings.")
        return redirect('home')

    if request.method == 'POST':
        form = BranchMappingForm(request.POST, instance=branch_mapping)
        if form.is_valid():
            form.save()
            messages.success(request, "Branch mapping updated successfully!")
            return HttpResponseRedirect(reverse('manage_branch_mappings', args=[company_slug]))
    else:
        form = BranchMappingForm(instance=branch_mapping)

    context = {
        'company': company,
        'branch_mapping': branch_mapping,
        'form': form,
    }

    return render(request, 'impairment/edit_branch_mapping.html', context)


@login_required
def manage_cbl_parameters(request, company_slug, project_slug):
    """Manage CBL parameters for a project"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to manage CBL parameters.")
        return redirect('home')

    cbl_parameters = project.cbl_parameters.all().order_by('loan_type', 'currency', 'risk_segment')

    context = {
        'company': company,
        'project': project,
        'cbl_parameters': cbl_parameters,
    }

    return render(request, 'impairment/manage_cbl_parameters.html', context)


@login_required
def add_cbl_parameters(request, company_slug, project_slug):
    """Add CBL parameters for a loan type/segment"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to add CBL parameters.")
        return redirect('home')

    if request.method == 'POST':
        form = CBLParametersForm(request.POST)
        if form.is_valid():
            cbl_params = form.save(commit=False)
            cbl_params.project = project
            cbl_params.created_by = request.user

            # Apply company defaults if not specified
            if not cbl_params.pd_floor:
                cbl_params.pd_floor = company.default_pd_floor
            if not cbl_params.lgd_floor:
                cbl_params.lgd_floor = company.default_lgd_floor
            if not cbl_params.lgd_ceiling:
                cbl_params.lgd_ceiling = company.default_lgd_ceiling

            cbl_params.save()
            messages.success(request, "CBL parameters added successfully!")
            return HttpResponseRedirect(reverse('manage_cbl_parameters', args=[company_slug, project_slug]))
    else:
        form = CBLParametersForm()
        # Pre-populate with company defaults
        form.initial.update({
            'pd_floor': company.default_pd_floor,
            'lgd_floor': company.default_lgd_floor,
            'lgd_ceiling': company.default_lgd_ceiling,
        })

    context = {
        'company': company,
        'project': project,
        'form': form,
    }

    return render(request, 'impairment/add_cbl_parameters.html', context)


@login_required
def edit_cbl_parameters(request, company_slug, project_slug, params_id):
    """Edit CBL parameters"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)
    cbl_params = get_object_or_404(CBLParameters, id=params_id, project=project)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to edit CBL parameters.")
        return redirect('home')

    if request.method == 'POST':
        form = CBLParametersForm(request.POST, instance=cbl_params)
        if form.is_valid():
            form.save()
            messages.success(request, "CBL parameters updated successfully!")
            return HttpResponseRedirect(reverse('manage_cbl_parameters', args=[company_slug, project_slug]))
    else:
        form = CBLParametersForm(instance=cbl_params)

    context = {
        'company': company,
        'project': project,
        'cbl_params': cbl_params,
        'form': form,
    }

    return render(request, 'impairment/edit_cbl_parameters.html', context)


@login_required
def upload_data(request, company_slug, project_slug):
    """Upload data files to a project"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to upload data.")
        return redirect('home')

    if request.method == 'POST':
        form = DataUploadForm(request.POST, request.FILES)
        if form.is_valid():
            data_upload = form.save(commit=False)
            data_upload.project = project
            data_upload.uploaded_by = request.user
            data_upload.save()

            # Update project flags based on upload type
            if data_upload.upload_type == 'loan_report':
                project.loan_report_uploaded = True
            elif data_upload.upload_type == 'arrears_report':
                project.arrears_report_uploaded = True

            project.status = 'data_upload'
            project.save()

            messages.success(request, f"{data_upload.get_upload_type_display()} uploaded successfully!")
            return HttpResponseRedirect(reverse('project_detail', args=[company_slug, project_slug]))
    else:
        form = DataUploadForm()

    context = {
        'company': company,
        'project': project,
        'form': form,
    }

    return render(request, 'impairment/upload_data.html', context)


@login_required
def update_company_parameters(request, company_slug):
    """Update company-level IFRS9 and CBL parameters"""
    company = get_object_or_404(Company, slug=company_slug)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to update company parameters.")
        return redirect('home')

    if request.method == 'POST':
        form = CompanyParametersUpdateForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, "Company parameters updated successfully!")
            return HttpResponseRedirect(reverse('company_detail', args=[company_slug]))
    else:
        form = CompanyParametersUpdateForm(instance=company)

    context = {
        'company': company,
        'form': form,
    }

    return render(request, 'impairment/update_company_parameters.html', context)


@login_required
def data_uploads_list(request, company_slug, project_slug):
    """List all data uploads for a project"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to view data uploads.")
        return redirect('home')

    uploads_list = project.data_uploads.all().order_by('-uploaded_at')
    paginator = Paginator(uploads_list, 20)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'company': company,
        'project': project,
        'page_obj': page_obj,
    }

    return render(request, 'impairment/data_uploads_list.html', context)


@login_required
@require_http_methods(["POST"])
def delete_branch_mapping(request, company_slug, mapping_id):
    """Delete a branch mapping"""
    company = get_object_or_404(Company, slug=company_slug)
    branch_mapping = get_object_or_404(BranchMapping, id=mapping_id, company=company)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to delete branch mappings.")
        return redirect('home')

    branch_mapping.delete()
    messages.success(request, "Branch mapping deleted successfully!")
    return HttpResponseRedirect(reverse('manage_branch_mappings', args=[company_slug]))


@login_required
@require_http_methods(["POST"])
def delete_cbl_parameters(request, company_slug, project_slug, params_id):
    """Delete CBL parameters"""
    company = get_object_or_404(Company, slug=company_slug)
    project = get_object_or_404(Project, slug=project_slug, company=company)
    cbl_params = get_object_or_404(CBLParameters, id=params_id, project=project)

    # Check permissions
    if not request.user.is_superuser and company.created_by != request.user:
        messages.error(request, "You don't have permission to delete CBL parameters.")
        return redirect('home')

    loan_type = cbl_params.loan_type
    cbl_params.delete()
    messages.success(request, f"CBL parameters for {loan_type} deleted successfully!")
    return HttpResponseRedirect(reverse('manage_cbl_parameters', args=[company_slug, project_slug]))


# @login_required
# def project_dashboard(request, company_slug, project_slug):
#     """Project dashboard with processing status and statistics"""
#     company = get_object_or_404(Company, slug=company_slug)
#     project = get_object_or_404(Project, slug=project_slug, company=company)
#
#     # Check permissions
#     if not request.user.is_superuser and company.created_by != request.user:
#         messages.error(request, "You don't have permission to view this project dashboard.")
#         return redirect('home')
#
#     # Get dashboard statistics
#     loan_accounts_count = project.loan_accounts.count()
#     arrears_accounts_count = project.arrears_accounts.count()
#
#     # Get staging distribution
#     stage_1_count = IFRS9Stage.objects.filter(
#         loan_account__project=project,
#         current_stage='stage_1'
#     ).count()
#     stage_2_count = IFRS9Stage.objects.filter(
#         loan_account__project=project,
#         current_stage='stage_2'
#     ).count()
#     stage_3_count = IFRS9Stage.objects.filter(
#         loan_account__project=project,
#         current_stage='stage_3'
#     ).count()
#
#     # Get ECL summary
#     total_ecl = ECLCalculation.objects.filter(
#         loan_account__project=project
#     ).aggregate(
#         total=models.Sum('final_ecl')
#     )['total'] or 0
#
#     context = {
#         'company': company,
#         'project': project,
#         'loan_accounts_count': loan_accounts_count,
#         'arrears_accounts_count': arrears_accounts_count,
#         'stage_1_count': stage_1_count,
#         'stage_2_count': stage_2_count,
#         'stage_3_count': stage_3_count,
#         'total_ecl': total_ecl,
#         'recent_uploads': project.data_uploads.all().order_by('-uploaded_at')[:3],
#     }
#
#     return render(request, 'impairment/project_dashboard.html', context)