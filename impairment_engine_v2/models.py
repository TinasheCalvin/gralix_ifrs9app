from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from decimal import Decimal
import uuid
from My_Users.models import MyUser
from datetime import date


class Company(models.Model):
    guid = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=200, blank=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    country = models.CharField(max_length=100, default='Zambia')
    base_currency = models.CharField(max_length=3, default='ZMW')

    # IFRS9 Configuration Presets
    stage_1_threshold_days = models.IntegerField(default=30, help_text="Days past due threshold for Stage 1")
    stage_2_threshold_days = models.IntegerField(default=90, help_text="Days past due threshold for Stage 2")
    sicr_threshold_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('50.00'),
        help_text="SICR threshold percentage for PD deterioration"
    )

    # CBL Computation Presets
    default_pd_floor = models.DecimalField(
        max_digits=10, decimal_places=6, default=Decimal('0.000100'),
        help_text="Minimum PD floor (0.01%)"
    )
    default_lgd_floor = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5.00'),
        help_text="Minimum LGD floor percentage"
    )
    default_lgd_ceiling = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('90.00'),
        help_text="Maximum LGD ceiling percentage"
    )

    # LGD Params
    gdp_value = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("3.00"))
    gdp_coefficient = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0.05"))

    # Operational settings
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class BranchMapping(models.Model):
    """Branch code mappings for each company - applies across all projects"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branch_mappings')
    branch_name = models.CharField(max_length=200)
    branch_code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'branch_code']
        ordering = ['branch_name']

    def __str__(self):
        return f"{self.company.name} - {self.branch_name} ({self.branch_code})"


class LGDRiskFactor(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='risk_factors')
    accessor_key = models.CharField(max_length=50, help_text="Key to match with loan data fields")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['company', 'accessor_key']
        unique_together = ['company', 'name']

    def __str__(self):
        return self.name


class LGDRiskFactorValue(models.Model):
    factor = models.ForeignKey(LGDRiskFactor, on_delete=models.CASCADE, related_name='values')
    name = models.CharField(max_length=100)  # Changed from 'value' to 'name'
    identifier = models.IntegerField(help_text="Unique LGD factor identifier e.g.")
    lgd_percentage = models.DecimalField(max_digits=7, decimal_places=2, help_text="Loss Given Default percentage (e.g., 40.23)")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['factor', 'name']
        unique_together = ["factor", "identifier"]

    def __str__(self):
        return f"{self.name} ({self.lgd_percentage}%)"


class OLSCoefficient(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    factor_value = models.ForeignKey(LGDRiskFactorValue, on_delete=models.CASCADE, null=True, blank=True)
    is_tenor = models.BooleanField(default=False)
    coefficient = models.DecimalField(max_digits=10, decimal_places=6)

    class Meta:
        unique_together = ['company', 'factor_value']


class Project(models.Model):
    """Projects within each company for different reporting periods"""
    STATUS_CHOICES = [
        ('setup', 'Initial Setup'),
        ('data_upload', 'Data Upload'),
        ('processing', 'Processing'),
        ('validation', 'Validation'),
        ('completed', 'Completed'),
        ('archived', 'Archived')
    ]

    guid = models.UUIDField(default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    reporting_date = models.DateField(help_text="As-of date for this analysis")

    # Project status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='setup')
    created_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Data upload flags
    loan_report_uploaded = models.BooleanField(default=False)
    arrears_report_uploaded = models.BooleanField(default=False)
    branch_mapping_applied = models.BooleanField(default=False)

    # NEW: Comprehensive JSON Data Storage
    loan_data = models.JSONField(
        default=dict, blank=True,
        help_text="Complete loan report data as JSON array"
    )
    arrears_data = models.JSONField(
        default=dict, blank=True,
        help_text="Complete arrears report data as JSON array"
    )

    # IFRS9 Processing Results as JSON
    ifrs9_staging_data = models.JSONField(
        default=dict, blank=True,
        help_text="IFRS9 staging results for all accounts"
    )
    ecl_calculation_data = models.JSONField(
        default=dict, blank=True,
        help_text="ECL calculation results for all accounts"
    )

    # Data validation and processing metadata
    data_validation_errors = models.JSONField(
        default=list, blank=True,
        help_text="Validation errors found in uploaded data"
    )
    data_processing_log = models.JSONField(
        default=list, blank=True,
        help_text="Log of data processing steps and transformations"
    )

    # Processing summary (computed from JSON data)
    total_loans = models.IntegerField(default=0)
    total_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_ecl = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    # IFRS9 Processing Results as JSON
    upload_metadata  = models.JSONField(
        default=dict, blank=True,
        help_text="Data Upload Metadata"
    )

    class Meta:
        unique_together = ['company', 'name']
        ordering = ['company', '-reporting_date', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.company.slug}-{self.name}-{self.reporting_date}")
        super().save(*args, **kwargs)

    def get_loan_accounts(self):
        """Get loan accounts from JSON data"""
        return self.loan_data.get('accounts', [])

    def get_arrears_accounts(self):
        """Get arrears accounts from JSON data"""
        return self.arrears_data.get('accounts', [])

    def get_loan_by_account_number(self, account_number):
        """Get specific loan account by account number"""
        loans = self.get_loan_accounts()
        return next((loan for loan in loans if loan.get('account_number') == account_number), None)

    def get_arrears_by_account_number(self, account_number):
        """Get specific arrears account by account number"""
        arrears = self.get_arrears_accounts()
        return next((arr for arr in arrears if arr.get('account_number') == account_number), None)

    def get_ifrs9_stages(self):
        """Get IFRS9 staging data from JSON"""
        return self.ifrs9_staging_data.get('stages', [])

    def get_ecl_calculations(self):
        """Get ECL calculation data from JSON"""
        return self.ecl_calculation_data.get('calculations', [])

    def get_ifrs9_stage_by_account(self, account_number):
        """Get IFRS9 stage for specific account"""
        stages = self.get_ifrs9_stages()
        return next((stage for stage in stages if stage.get('account_number') == account_number), None)

    def get_ecl_calculation_by_account(self, account_number):
        """Get ECL calculation for specific account"""
        calculations = self.get_ecl_calculations()
        return next((calc for calc in calculations if calc.get('account_number') == account_number), None)

    def update_processing_summary(self):
        """Update summary fields from JSON data"""
        loans = self.get_loan_accounts()
        ecl_calculations = self.get_ecl_calculations()

        self.total_loans = len(loans)
        self.total_exposure = sum(Decimal(str(loan.get('balance', 0))) for loan in loans)
        self.total_ecl = sum(Decimal(str(calc.get('final_ecl', 0))) for calc in ecl_calculations)
        self.save(update_fields=['total_loans', 'total_exposure', 'total_ecl'])

    def update_ifrs9_stage(self, account_number, stage_data):
        """Update or add IFRS9 stage for an account"""
        stages = self.get_ifrs9_stages()
        existing_stage = next((i for i, stage in enumerate(stages)
                               if stage.get('account_number') == account_number), None)

        if existing_stage is not None:
            stages[existing_stage] = stage_data
        else:
            stages.append(stage_data)

        self.ifrs9_staging_data['stages'] = stages
        self.save(update_fields=['ifrs9_staging_data'])

    def update_ecl_calculation(self, account_number, ecl_data):
        """Update or add ECL calculation for an account"""
        calculations = self.get_ecl_calculations()
        existing_calc = next((i for i, calc in enumerate(calculations)
                              if calc.get('account_number') == account_number), None)

        if existing_calc is not None:
            calculations[existing_calc] = ecl_data
        else:
            calculations.append(ecl_data)

        self.ecl_calculation_data['calculations'] = calculations
        self.save(update_fields=['ecl_calculation_data'])

    def __str__(self):
        return f"{self.name} - ({self.reporting_date})"


class IFRS9StageSummary(models.Model):
    """Simplified staging summary for reporting and complex queries"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='stage_summaries')

    # Summary by stage
    stage_1_count = models.IntegerField(default=0)
    stage_1_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    stage_1_ecl = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    stage_2_count = models.IntegerField(default=0)
    stage_2_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    stage_2_ecl = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    stage_3_count = models.IntegerField(default=0)
    stage_3_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    stage_3_ecl = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    # Movement summary
    stage_1_to_2_count = models.IntegerField(default=0)
    stage_2_to_1_count = models.IntegerField(default=0)
    stage_2_to_3_count = models.IntegerField(default=0)
    stage_3_to_2_count = models.IntegerField(default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['project']

    def refresh_from_json(self):
        """Refresh summary from project's JSON data"""
        stages = self.project.get_ifrs9_stages()
        ecl_calcs = self.project.get_ecl_calculations()

        # Create lookup for ECL by account
        ecl_lookup = {calc['account_number']: calc for calc in ecl_calcs}

        # Reset counters
        self.stage_1_count = self.stage_1_exposure = self.stage_1_ecl = 0
        self.stage_2_count = self.stage_2_exposure = self.stage_2_ecl = 0
        self.stage_3_count = self.stage_3_exposure = self.stage_3_ecl = 0

        for stage in stages:
            account_number = stage.get('account_number')
            current_stage = stage.get('current_stage')

            # Get loan and ECL data
            loan = self.project.get_loan_by_account_number(account_number)
            ecl = ecl_lookup.get(account_number, {})

            exposure = Decimal(str(loan.get('balance', 0))) if loan else 0
            ecl_amount = Decimal(str(ecl.get('final_ecl', 0)))

            if current_stage == 'stage_1':
                self.stage_1_count += 1
                self.stage_1_exposure += exposure
                self.stage_1_ecl += ecl_amount
            elif current_stage == 'stage_2':
                self.stage_2_count += 1
                self.stage_2_exposure += exposure
                self.stage_2_ecl += ecl_amount
            elif current_stage == 'stage_3':
                self.stage_3_count += 1
                self.stage_3_exposure += exposure
                self.stage_3_ecl += ecl_amount

        self.save()


class ECLSummary(models.Model):
    """ECL summary by segment for reporting"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='ecl_summaries')

    # Segmentation
    loan_type = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)

    # Summary metrics
    account_count = models.IntegerField(default=0)
    total_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_ecl_12m = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_ecl_lifetime = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_final_ecl = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    # Coverage ratios
    ecl_coverage_ratio = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['project', 'loan_type', 'currency']

    def refresh_from_json(self):
        """Refresh summary from project's JSON data"""
        loans = self.project.get_loan_accounts()
        ecl_calcs = self.project.get_ecl_calculations()

        # Filter for this segment
        segment_loans = [loan for loan in loans
                         if loan.get('loan_type') == self.loan_type
                         and loan.get('currency') == self.currency]

        segment_ecls = [ecl for ecl in ecl_calcs
                        if any(loan.get('account_number') == ecl.get('account_number')
                               for loan in segment_loans)]

        self.account_count = len(segment_loans)
        self.total_exposure = sum(Decimal(str(loan.get('balance', 0))) for loan in segment_loans)
        self.total_ecl_12m = sum(Decimal(str(ecl.get('ecl_12_month', 0))) for ecl in segment_ecls)
        self.total_ecl_lifetime = sum(Decimal(str(ecl.get('ecl_lifetime', 0))) for ecl in segment_ecls)
        self.total_final_ecl = sum(Decimal(str(ecl.get('final_ecl', 0))) for ecl in segment_ecls)

        if self.total_exposure > 0:
            self.ecl_coverage_ratio = (self.total_final_ecl / self.total_exposure) * 100

        self.save()


class CBLParameters(models.Model):
    """CBL parameters by loan type/segment for PD, LGD, EAD calculations"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='cbl_parameters')
    slug = models.SlugField(max_length=200, blank=True)

    # Segmentation
    loan_type = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    risk_segment = models.CharField(max_length=50, blank=True, default='standard')

    # PD (Probability of Default) parameters
    pd_12_month = models.DecimalField(
        max_digits=10, decimal_places=6,
        help_text="12-month PD for Stage 1"
    )
    pd_lifetime = models.DecimalField(
        max_digits=10, decimal_places=6,
        help_text="Lifetime PD for Stage 2/3"
    )
    pd_floor = models.DecimalField(
        max_digits=10, decimal_places=6,
        help_text="Minimum PD floor"
    )

    # LGD (Loss Given Default) parameters
    lgd_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Base LGD rate %"
    )
    lgd_floor = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Minimum LGD %"
    )
    lgd_ceiling = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Maximum LGD %"
    )

    # EAD (Exposure at Default) parameters
    ccf_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Credit Conversion Factor for undrawn commitments"
    )

    # Recovery and timing
    recovery_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Expected recovery rate %"
    )
    recovery_time_months = models.IntegerField(
        default=36,
        help_text="Expected time to recover in months"
    )

    # Discounting
    discount_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Discount rate for PV calculations"
    )

    # Macro-economic adjustments
    macro_adjustment_factor = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.00,
        help_text="Macro-economic adjustment factor"
    )

    # Forward-looking adjustments
    forward_looking_adjustment = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Forward-looking adjustment %"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['project', 'loan_type', 'currency', 'risk_segment']
        ordering = ['loan_type', 'currency']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.project.slug}-params-{self.loan_type}-{self.currency}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project.name} - {self.loan_type} ({self.currency})"


class DataUpload(models.Model):
    """Track file uploads for each project"""
    UPLOAD_TYPES = [
        ('loan_report', 'Loan Report'),
        ('arrears_report', 'Arrears Report'),
        ('branch_mapping', 'Branch Mapping'),
        ('cbl_parameters', 'CBL Parameters')
    ]

    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partially_failed', 'Partially Failed')
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='data_uploads')

    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPES)
    file_name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='uploads/%Y/%m/')

    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    records_processed = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    error_log = models.TextField(blank=True)
    validation_errors = models.JSONField(default=list, blank=True)

    raw_data_sample = models.JSONField(
        default=dict, blank=True,
        help_text="Sample of raw uploaded data for debugging"
    )

    # Upload metadata
    uploaded_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.project.name} - {self.upload_type} - {self.file_name}"



class DataValidationRule(models.Model):
    """Define validation rules for loan and arrears data"""
    RULE_TYPES = [
        ('required_field', 'Required Field'),
        ('data_type', 'Data Type Validation'),
        ('range_check', 'Range/Boundary Check'),
        ('format_check', 'Format Validation'),
        ('business_rule', 'Business Logic Rule'),
        ('cross_reference', 'Cross-Reference Check')
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='validation_rules')
    rule_name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    data_type = models.CharField(max_length=20, choices=[('loan', 'Loan Data'), ('arrears', 'Arrears Data')])

    # Rule configuration
    field_name = models.CharField(max_length=50)
    validation_config = models.JSONField(
        default=dict,
        help_text="Configuration for the validation rule (e.g., min/max values, regex patterns)"
    )

    error_message = models.TextField(help_text="Error message to display when validation fails")
    is_active = models.BooleanField(default=True)
    severity = models.CharField(
        max_length=10,
        choices=[('error', 'Error'), ('warning', 'Warning'), ('info', 'Info')],
        default='error'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['company', 'rule_name', 'data_type']
        ordering = ['data_type', 'rule_name']

    def __str__(self):
        return f"{self.company.name} - {self.rule_name} ({self.data_type})"