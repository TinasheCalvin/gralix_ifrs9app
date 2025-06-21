from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from decimal import Decimal
import uuid
from My_Users.models import MyUser

class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100, default='Zambia')
    base_currency = models.CharField(max_length=3, default='ZMW')

    # IFRS9 Configuration Presets
    stage_1_threshold_days = models.IntegerField(default=30, help_text="Days past due threshold for Stage 2")
    stage_2_threshold_days = models.IntegerField(default=90, help_text="Days past due threshold for Stage 3")
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

    # Operational settings
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['name']

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200)
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

    # Processing summary
    total_loans = models.IntegerField(default=0)
    total_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_ecl = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        unique_together = ['company', 'name']
        ordering = ['company', '-reporting_date', 'name']

    def __str__(self):
        return f"{self.company.name} - {self.name} ({self.reporting_date})"


class LoanAccount(models.Model):
    """Standardized loan account data from loan reports"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='loan_accounts')

    # Core identifiers - standardized
    account_number = models.CharField(max_length=50, db_index=True, help_text="Account/Contract Number")

    # Branch information
    branch = models.CharField(max_length=200)
    branch_code = models.CharField(max_length=20, blank=True)

    # Client information - standardized
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)

    # Loan details - standardized
    loan_type = models.CharField(max_length=100)
    opening_date = models.DateField()
    maturity_date = models.DateField()

    # Financial details - standardized
    currency = models.CharField(max_length=3)
    loan_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Original loan amount")
    installment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    balance = models.DecimalField(max_digits=15, decimal_places=2, help_text="Outstanding balance")
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual interest rate %")
    insurance_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Derived fields for CBL computation
    days_to_maturity = models.IntegerField(blank=True, null=True)
    original_term_months = models.IntegerField(blank=True, null=True)
    remaining_term_months = models.IntegerField(blank=True, null=True)

    # Risk indicators
    is_restructured = models.BooleanField(default=False)
    is_refinanced = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['project', 'account_number']
        indexes = [
            models.Index(fields=['project', 'account_number']),
            models.Index(fields=['loan_type', 'currency']),
            models.Index(fields=['opening_date', 'maturity_date']),
        ]

    def save(self, *args, **kwargs):
        # Calculate derived fields
        if self.opening_date and self.maturity_date:
            self.days_to_maturity = (self.maturity_date - date.today()).days
            self.original_term_months = (self.maturity_date.year - self.opening_date.year) * 12 + \
                                        (self.maturity_date.month - self.opening_date.month)
            self.remaining_term_months = (self.maturity_date.year - date.today().year) * 12 + \
                                         (self.maturity_date.month - date.today().month)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_number} - {self.firstname} {self.lastname}"


class ArrearsAccount(models.Model):
    """Standardized arrears data - subset of loans in default"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='arrears_accounts')
    loan_account = models.ForeignKey(
        LoanAccount, on_delete=models.CASCADE, related_name='arrears_data',
        help_text="Link to corresponding loan account"
    )

    # Core arrears data - standardized
    account_number = models.CharField(max_length=50, db_index=True)
    client_name = models.CharField(max_length=200)
    currency = models.CharField(max_length=3)
    capital_balance = models.DecimalField(max_digits=15, decimal_places=2)
    arrears_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Amount in arrears")
    exposure = models.DecimalField(max_digits=15, decimal_places=2, help_text="Capital balance + arrears")

    # Additional fields needed for staging
    days_past_due = models.IntegerField(help_text="Days past due for staging")
    first_delinquency_date = models.DateField(blank=True, null=True)
    last_payment_date = models.DateField(blank=True, null=True)
    last_payment_amount = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)

    # Restructuring/forbearance indicators for staging
    is_restructured = models.BooleanField(default=False)
    restructure_date = models.DateField(blank=True, null=True)
    forbearance_granted = models.BooleanField(default=False)

    # # Collection status
    # legal_action_initiated = models.BooleanField(default=False)
    # legal_action_date = models.DateField(blank=True, null=True)
    # collateral_status = models.CharField(max_length=50, blank=True)
    #
    # # Provisioning (if existing)
    # existing_provision = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['project', 'account_number']
        indexes = [
            models.Index(fields=['days_past_due']),
            models.Index(fields=['first_delinquency_date']),
        ]

    def __str__(self):
        return f"{self.account_number} - {self.days_past_due} DPD - {self.exposure}"


class IFRS9Stage(models.Model):
    """IFRS9 Stage classification for each loan"""
    STAGE_CHOICES = [
        ('stage_1', 'Stage 1 - 12-month ECL'),
        ('stage_2', 'Stage 2 - Lifetime ECL (not credit-impaired)'),
        ('stage_3', 'Stage 3 - Lifetime ECL (credit-impaired)'),
        ('poci', 'POCI - Purchased or Originated Credit-Impaired')
    ]

    loan_account = models.OneToOneField(LoanAccount, on_delete=models.CASCADE, related_name='ifrs9_stage')

    # Current stage classification
    current_stage = models.CharField(max_length=10, choices=STAGE_CHOICES)
    previous_stage = models.CharField(max_length=10, blank=True)
    stage_movement_date = models.DateField(blank=True, null=True)

    # Staging criteria met
    dpd_criteria_met = models.BooleanField(default=False, help_text="Days past due criteria")
    sicr_criteria_met = models.BooleanField(default=False, help_text="SICR criteria")
    qualitative_criteria_met = models.BooleanField(default=False, help_text="Qualitative criteria")

    # SICR indicators
    sicr_reason = models.TextField(blank=True)
    pd_deterioration_factor = models.DecimalField(
        max_digits=10, decimal_places=4, blank=True, null=True,
        help_text="Factor by which PD has increased"
    )

    # Qualitative factors
    restructured = models.BooleanField(default=False)
    forbearance_applied = models.BooleanField(default=False)
    watch_list = models.BooleanField(default=False)

    # Quantitative factors
    days_past_due = models.IntegerField(default=0)
    consecutive_missed_payments = models.IntegerField(default=0)

    # Staging decision audit
    staging_rationale = models.TextField(blank=True, help_text="Rationale for staging decision")
    auto_staged = models.BooleanField(default=True, help_text="Automatically staged vs manual override")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.loan_account.account_number} - {self.current_stage}"


class CBLParameters(models.Model):
    """CBL parameters by loan type/segment for PD, LGD, EAD calculations"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='cbl_parameters')

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

    def __str__(self):
        return f"{self.project.name} - {self.loan_type} ({self.currency})"


class ECLCalculation(models.Model):
    """Individual ECL calculations for each loan"""
    loan_account = models.OneToOneField(LoanAccount, on_delete=models.CASCADE, related_name='ecl_calculation')

    # EAD (Exposure at Default)
    ead_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Exposure at Default"
    )
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2)
    undrawn_commitment = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Applied rates from parameters
    applied_pd_12m = models.DecimalField(max_digits=10, decimal_places=6)
    applied_pd_lifetime = models.DecimalField(max_digits=10, decimal_places=6)
    applied_lgd = models.DecimalField(max_digits=5, decimal_places=2)

    # ECL components
    ecl_12_month = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="12-month ECL (Stage 1)"
    )
    ecl_lifetime = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Lifetime ECL (Stage 2/3)"
    )

    # Final ECL based on IFRS9 stage
    final_ecl = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Final ECL based on staging"
    )

    # Supporting calculations
    present_value_factor = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    macro_adjustment = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    forward_looking_adjustment = models.DecimalField(max_digits=10, decimal_places=6, default=1)

    # Calculation metadata
    calculation_method = models.CharField(
        max_length=50,
        choices=[
            ('collective', 'Collective Assessment'),
            ('individual', 'Individual Assessment'),
            ('simplified', 'Simplified Approach')
        ],
        default='collective'
    )
    calculation_date = models.DateTimeField(auto_now=True)

    # ECL coverage ratio
    ecl_coverage_ratio = models.DecimalField(
        max_digits=10, decimal_places=6, blank=True, null=True,
        help_text="ECL as % of exposure"
    )

    def save(self, *args, **kwargs):
        # Calculate ECL coverage ratio
        if self.ead_amount > 0:
            self.ecl_coverage_ratio = (self.final_ecl / self.ead_amount) * 100
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.loan_account.account_number} - ECL: {self.final_ecl}"


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

    # Upload metadata
    uploaded_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.project.name} - {self.upload_type} - {self.file_name}"



