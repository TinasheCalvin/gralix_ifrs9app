from django.contrib import admin
from .models import (
    Company, BranchMapping, Project, LoanAccount, ArrearsAccount,
    IFRS9Stage, CBLParameters, ECLCalculation, DataUpload
)


@admin.register(Company)
class CompanyV2Admin(admin.ModelAdmin):
    list_display = ['name', 'country', 'base_currency', 'is_active', 'created_at']
    list_filter = ['country', 'base_currency', 'is_active']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'country', 'base_currency', 'is_active')
        }),
        ('IFRS9 Configuration', {
            'fields': (
                'stage_1_threshold_days', 'stage_2_threshold_days', 'sicr_threshold_percent',
                'default_pd_floor', 'default_lgd_floor', 'default_lgd_ceiling'
            )
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BranchMapping)
class BranchMappingAdmin(admin.ModelAdmin):
    list_display = ['company', 'branch_name', 'branch_code', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['branch_name', 'branch_code']
    readonly_fields = ['created_at']


@admin.register(Project)
class ProjectV2Admin(admin.ModelAdmin):
    list_display = ['name', 'company', 'reporting_date', 'status', 'total_loans', 'total_exposure', 'total_ecl']
    list_filter = ['status', 'company', 'reporting_date']
    search_fields = ['name', 'company__name']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('Project Information', {
            'fields': ('company', 'name', 'description', 'reporting_date', 'status')
        }),
        ('Data Upload Status', {
            'fields': ('loan_report_uploaded', 'arrears_report_uploaded', 'branch_mapping_applied')
        }),
        ('Summary Statistics', {
            'fields': ('total_loans', 'total_exposure', 'total_ecl'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LoanAccount)
class LoanAccountAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'project', 'firstname', 'lastname', 'loan_type', 'balance', 'currency']
    list_filter = ['project', 'loan_type', 'currency', 'is_restructured']
    search_fields = ['account_number', 'firstname', 'lastname']
    readonly_fields = ['created_at', 'updated_at', 'days_to_maturity', 'original_term_months', 'remaining_term_months']

    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'account_number', 'branch', 'branch_code')
        }),
        ('Client Information', {
            'fields': ('firstname', 'lastname')
        }),
        ('Loan Details', {
            'fields': ('loan_type', 'opening_date', 'maturity_date', 'currency')
        }),
        ('Financial Information', {
            'fields': ('loan_amount', 'installment_amount', 'balance', 'interest_rate', 'insurance_fees')
        }),
        ('Risk Indicators', {
            'fields': ('is_restructured', 'is_refinanced')
        }),
        ('Calculated Fields', {
            'fields': ('days_to_maturity', 'original_term_months', 'remaining_term_months'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ArrearsAccount)
class ArrearsAccountAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'client_name', 'days_past_due', 'exposure', 'currency']
    list_filter = ['project', 'currency', 'is_restructured', 'forbearance_granted']
    search_fields = ['account_number', 'client_name']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'loan_account', 'account_number', 'client_name', 'currency')
        }),
        ('Financials', {
            'fields': ('capital_balance', 'arrears_amount', 'exposure')
        }),
        ('Delinquency', {
            'fields': ('days_past_due', 'first_delinquency_date', 'last_payment_date', 'last_payment_amount')
        }),
        ('Restructuring/Forbearance', {
            'fields': ('is_restructured', 'restructure_date', 'forbearance_granted')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(IFRS9Stage)
class IFRS9StageAdmin(admin.ModelAdmin):
    list_display = ['loan_account', 'current_stage', 'previous_stage', 'stage_movement_date']
    list_filter = ['current_stage', 'auto_staged', 'dpd_criteria_met', 'sicr_criteria_met']
    search_fields = ['loan_account__account_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CBLParameters)
class CBLParametersAdmin(admin.ModelAdmin):
    list_display = ['project', 'loan_type', 'currency', 'risk_segment', 'pd_12_month', 'lgd_rate']
    list_filter = ['project', 'currency', 'loan_type']
    search_fields = ['loan_type', 'risk_segment']
    readonly_fields = ['created_at']


@admin.register(ECLCalculation)
class ECLCalculationAdmin(admin.ModelAdmin):
    list_display = ['loan_account', 'ead_amount', 'final_ecl', 'ecl_coverage_ratio', 'calculation_method']
    list_filter = ['calculation_method']
    search_fields = ['loan_account__account_number']
    readonly_fields = ['calculation_date', 'ecl_coverage_ratio']


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = ['project', 'upload_type', 'file_name', 'status', 'records_processed', 'records_failed',
                    'uploaded_at']
    list_filter = ['upload_type', 'status', 'project']
    search_fields = ['file_name', 'project__name']
    readonly_fields = ['uploaded_at', 'processed_at']
