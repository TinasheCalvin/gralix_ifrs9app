from django.contrib import admin
from .models import HistoricalCustomerLoanData, Project, PDCalculationResult, EADLGDCalculationResult, ECLCalculationResult, CurrentLoanBook, Company

# Register your models here.
@admin.register(HistoricalCustomerLoanData)
class HistoricalCustomerLoanDataAdmin(admin.ModelAdmin):
    list_display = ('project', 'file_name', 'file_upload_date', 'is_valid')
    exclude = ['uploaded_file']


@admin.register(Company)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at', 'created_by']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_date', 'created_by', 'status']

@admin.register(PDCalculationResult)
class PDCalculationResultAdmin(admin.ModelAdmin):
    list_display = ('project', 'base_transition_matrix', 'stage_1_cumulative', 'stage_2_cumulative', 'stage_1_marginal', 'stage_2_marginal', 'cures', 'recoveries')


@admin.register(EADLGDCalculationResult)
class EADLGDCalculationResultAdmin(admin.ModelAdmin):
    list_display = ['project', 'account_no', 'stage', 'loan_type', 'effective_interest_rate', 'amortization_schedule', 'lgd_schedule', 'created_at']


@admin.register(CurrentLoanBook)
class CurrentLoanBookAdmin(admin.ModelAdmin):
    list_display = ['project', 'file_name', 'file_upload_date', 'is_valid']
    exclude = ['uploaded_file']


@admin.register(ECLCalculationResult)
class ECLCalculationResultAdmin(admin.ModelAdmin):
    list_display = ['project', 'created_at']
    exclude = ['ecl_results']