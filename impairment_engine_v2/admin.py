from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Sum
from .models import (
    Company, BranchMapping, Project, IFRS9StageSummary,
    ECLSummary, CBLParameters, DataUpload, DataValidationRule
)


# Custom Filters
class StatusFilter(SimpleListFilter):
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return Project.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class UploadTypeFilter(SimpleListFilter):
    title = 'Upload Type'
    parameter_name = 'upload_type'

    def lookups(self, request, model_admin):
        return DataUpload.UPLOAD_TYPES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(upload_type=self.value())
        return queryset


# Inline Admin Classes
class BranchMappingInline(admin.TabularInline):
    model = BranchMapping
    extra = 1
    fields = ['branch_name', 'branch_code', 'is_active']
    ordering = ['branch_name']


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0
    fields = ['name', 'reporting_date', 'status']
    readonly_fields = ['status']
    show_change_link = True


# Main Admin Classes
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'base_currency', 'is_active', 'created_at')
    list_filter = ('country', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ['name']}
    inlines = [BranchMappingInline, ProjectInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'slug', 'country', 'base_currency', 'is_active')
        }),
        ('IFRS9 Configuration', {
            'fields': (
                'stage_1_threshold_days',
                'stage_2_threshold_days',
                'sicr_threshold_percent'
            ),
            'classes': ('collapse',)
        }),
        ('CBL Computation Presets', {
            'fields': (
                'default_pd_floor',
                'default_lgd_floor',
                'default_lgd_ceiling'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('created_at',)
        return self.readonly_fields


@admin.register(BranchMapping)
class BranchMappingAdmin(admin.ModelAdmin):
    list_display = ('company', 'branch_name', 'branch_code', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('branch_name', 'branch_code')
    list_editable = ('is_active',)
    ordering = ('company', 'branch_name')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'company', 'reporting_date', 'status',
        'loan_report_uploaded', 'arrears_report_uploaded',
        'total_loans', 'total_exposure', 'total_ecl'
    )
    list_filter = ('company', StatusFilter, 'reporting_date')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = (
        'created_at', 'updated_at', 'total_loans',
        'total_exposure', 'total_ecl', 'data_processing_log'
    )
    fieldsets = (
        (None, {
            'fields': ('company', 'name', 'slug', 'description', 'reporting_date', 'status')
        }),
        ('Data Upload Status', {
            'fields': (
                'loan_report_uploaded',
                'arrears_report_uploaded',
                'branch_mapping_applied'
            ),
            'classes': ('collapse',)
        }),
        ('Data Storage', {
            'fields': (
                'loan_data',
                'arrears_data',
                'ifrs9_staging_data',
                'ecl_calculation_data'
            ),
            'classes': ('collapse',)
        }),
        ('Validation & Processing', {
            'fields': (
                'data_validation_errors',
                'data_processing_log'
            ),
            'classes': ('collapse',)
        }),
        ('Summary Metrics', {
            'fields': (
                'total_loans',
                'total_exposure',
                'total_ecl'
            )
        }),
        ('Schema Versions', {
            'fields': (
                'loan_data_schema_version',
                'arrears_data_schema_version',
                'ifrs9_staging_schema_version',
                'ecl_calculation_schema_version'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_exposure_sum=Sum('total_exposure'),
            total_ecl_sum=Sum('total_ecl')
        )

    def total_exposure(self, obj):
        return f"{obj.total_exposure:,.2f} {obj.company.base_currency}"

    total_exposure.admin_order_field = 'total_exposure_sum'

    def total_ecl(self, obj):
        return f"{obj.total_ecl:,.2f} {obj.company.base_currency}"

    total_ecl.admin_order_field = 'total_ecl_sum'


@admin.register(IFRS9StageSummary)
class IFRS9StageSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'project',
        'stage_1_count', 'stage_1_exposure', 'stage_1_ecl',
        'stage_2_count', 'stage_2_exposure', 'stage_2_ecl',
        'stage_3_count', 'stage_3_exposure', 'stage_3_ecl',
        'last_updated'
    )
    list_filter = ('project__company', 'project')
    readonly_fields = ('last_updated',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project', 'project__company')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == 'GET'


@admin.register(ECLSummary)
class ECLSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'loan_type', 'currency',
        'account_count', 'total_exposure', 'total_final_ecl',
        'ecl_coverage_ratio', 'last_updated'
    )
    list_filter = ('project__company', 'project', 'loan_type', 'currency')
    search_fields = ('loan_type', 'currency')
    readonly_fields = ('last_updated', 'ecl_coverage_ratio')

    def ecl_coverage_percent(self, obj):
        return f"{obj.ecl_coverage_ratio:.2f}%"

    ecl_coverage_percent.short_description = 'ECL Coverage'
    ecl_coverage_percent.admin_order_field = 'ecl_coverage_ratio'


@admin.register(CBLParameters)
class CBLParametersAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'loan_type', 'currency', 'risk_segment',
        'pd_12_month', 'pd_lifetime', 'lgd_rate'
    )
    list_filter = ('project__company', 'project', 'loan_type', 'currency')
    search_fields = ('loan_type', 'currency', 'risk_segment')
    prepopulated_fields = {'slug': ['project', 'loan_type', 'currency']}
    fieldsets = (
        (None, {
            'fields': ('project', 'slug', 'loan_type', 'currency', 'risk_segment')
        }),
        ('PD Parameters', {
            'fields': (
                'pd_12_month',
                'pd_lifetime',
                'pd_floor'
            )
        }),
        ('LGD Parameters', {
            'fields': (
                'lgd_rate',
                'lgd_floor',
                'lgd_ceiling'
            )
        }),
        ('EAD & Recovery', {
            'fields': (
                'ccf_rate',
                'recovery_rate',
                'recovery_time_months'
            )
        }),
        ('Adjustments', {
            'fields': (
                'discount_rate',
                'macro_adjustment_factor',
                'forward_looking_adjustment'
            )
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = (
        'file_name', 'project', 'upload_type',
        'status', 'records_processed', 'records_failed',
        'uploaded_at', 'processed_at'
    )
    list_filter = ('project__company', 'project', UploadTypeFilter, 'status')
    search_fields = ('file_name', 'project__name')
    readonly_fields = (
        'uploaded_at', 'processed_at', 'records_processed',
        'records_failed', 'error_log', 'validation_errors'
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('project', 'upload_type', 'file_path')
        return self.readonly_fields


@admin.register(DataValidationRule)
class DataValidationRuleAdmin(admin.ModelAdmin):
    list_display = (
        'rule_name', 'company', 'rule_type', 'data_type',
        'field_name', 'severity', 'is_active'
    )
    list_filter = ('company', 'rule_type', 'data_type', 'severity', 'is_active')
    search_fields = ('rule_name', 'field_name', 'error_message')
    list_editable = ('is_active', 'severity')
    fieldsets = (
        (None, {
            'fields': ('company', 'rule_name', 'is_active')
        }),
        ('Rule Configuration', {
            'fields': (
                'rule_type',
                'data_type',
                'field_name',
                'validation_config'
            )
        }),
        ('Error Handling', {
            'fields': (
                'error_message',
                'severity'
            )
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )