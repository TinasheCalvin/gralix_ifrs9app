from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Company, Project, BranchMapping, CBLParameters,
    DataUpload, LGDRiskFactor, LGDRiskFactorValue
)


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company Name',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description (optional)',
                'rows': 3
            }),
        }
        labels = {
            'name': 'Company Name',
            'description': 'Description (optional)'
        }


class LGDRiskFactorForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., Client Type, Collateral Type, Industry Sector'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Brief description of this risk factor and how it affects LGD calculations',
            'rows': 3
        }),
        required=False
    )

    class Meta:
        model = LGDRiskFactor
        fields = ['name', 'description']


class LGDRiskFactorValueForm(forms.ModelForm):
    coefficient = forms.DecimalField(
        max_digits=10, decimal_places=6, required=False,
        label="OLS Coefficient (Optional)",
        help_text="If you're using OLS-based LGD, provide a coefficient"
    )

    class Meta:
        model = LGDRiskFactorValue
        fields = ['name', 'lgd_percentage']

    def save(self, commit=True):
        instance = super().save(commit=False)
        self.cleaned_coefficient = self.cleaned_data.get('coefficient')
        if commit:
            instance.save()
        return instance


class ProjectForm(forms.ModelForm):
    """Form for creating and editing projects"""

    class Meta:
        model = Project
        fields = ['name', 'description', 'reporting_date']

        widgets = {
            'reporting_date': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Select Reporting Date',
                    'type': 'date'
                }
            ),
            'description': forms.Textarea(attrs={'rows': 3})
        }

    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)

        self.fields['name'].widget.attrs['class'] = 'form-control'
        self.fields['name'].widget.attrs['placeholder'] = 'Enter Project Name'
        self.fields['name'].label = 'Project Name'

        self.fields['description'].widget.attrs['class'] = 'form-control'
        self.fields['description'].widget.attrs['placeholder'] = 'Enter project description (optional)'
        self.fields['description'].label = 'Description'
        self.fields['description'].required = False

        self.fields['reporting_date'].widget.attrs['class'] = 'form-control'
        self.fields['reporting_date'].widget.attrs['placeholder'] = 'Select Reporting Date'
        self.fields['reporting_date'].label = 'Reporting Date'


class BranchMappingForm(forms.ModelForm):
    """Form for adding individual branch mappings"""

    class Meta:
        model = BranchMapping
        fields = ['branch_name', 'branch_code', 'is_active']

        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super(BranchMappingForm, self).__init__(*args, **kwargs)

        self.fields['branch_name'].widget.attrs['class'] = 'form-control'
        self.fields['branch_name'].widget.attrs['placeholder'] = 'Enter Branch Name'
        self.fields['branch_name'].label = 'Branch Name'

        self.fields['branch_code'].widget.attrs['class'] = 'form-control'
        self.fields['branch_code'].widget.attrs['placeholder'] = 'Enter Branch Code'
        self.fields['branch_code'].label = 'Branch Code'

        self.fields['is_active'].label = 'Active'


class BranchMappingBulkForm(forms.Form):
    """Form for bulk uploading branch mappings via CSV"""

    csv_file = forms.FileField(
        label='Branch Mapping CSV File',
        help_text='Upload CSV with columns: branch_name, branch_code, is_active (optional)',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv',
        })
    )

    def clean_csv_file(self):
        file = self.cleaned_data['csv_file']
        if not file.name.endswith('.csv'):
            raise ValidationError('File must be a CSV file')
        if file.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError('File size must be less than 5MB')
        return file


class CBLParametersForm(forms.ModelForm):
    """Form for configuring CBL parameters by loan type/segment"""

    class Meta:
        model = CBLParameters
        fields = [
            'loan_type', 'currency', 'risk_segment',
            'pd_12_month', 'pd_lifetime', 'pd_floor',
            'lgd_rate', 'lgd_floor', 'lgd_ceiling',
            'ccf_rate', 'recovery_rate', 'recovery_time_months',
            'discount_rate', 'macro_adjustment_factor', 'forward_looking_adjustment'
        ]

        widgets = {
            'pd_12_month': forms.NumberInput(attrs={'step': '0.000001', 'min': '0'}),
            'pd_lifetime': forms.NumberInput(attrs={'step': '0.000001', 'min': '0'}),
            'pd_floor': forms.NumberInput(attrs={'step': '0.000001', 'min': '0'}),
            'lgd_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'lgd_floor': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'lgd_ceiling': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'ccf_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'recovery_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'recovery_time_months': forms.NumberInput(attrs={'min': '1'}),
            'discount_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'macro_adjustment_factor': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'forward_looking_adjustment': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super(CBLParametersForm, self).__init__(*args, **kwargs)

        # Segmentation fields
        self.fields['loan_type'].widget.attrs['class'] = 'form-control'
        self.fields['loan_type'].widget.attrs['placeholder'] = 'e.g., Personal Loan, Mortgage'
        self.fields['loan_type'].label = 'Loan Type'

        self.fields['currency'].widget.attrs['class'] = 'form-control'
        self.fields['currency'].widget.attrs['placeholder'] = 'e.g., ZMW, USD'
        self.fields['currency'].label = 'Currency'

        self.fields['risk_segment'].widget.attrs['class'] = 'form-control'
        self.fields['risk_segment'].widget.attrs['placeholder'] = 'e.g., standard, prime, subprime'
        self.fields['risk_segment'].label = 'Risk Segment'

        # PD parameters
        self.fields['pd_12_month'].widget.attrs['class'] = 'form-control'
        self.fields['pd_12_month'].widget.attrs['placeholder'] = '0.050000'
        self.fields['pd_12_month'].label = '12-Month PD'
        self.fields['pd_12_month'].help_text = 'Probability of default within 12 months'

        self.fields['pd_lifetime'].widget.attrs['class'] = 'form-control'
        self.fields['pd_lifetime'].widget.attrs['placeholder'] = '0.150000'
        self.fields['pd_lifetime'].label = 'Lifetime PD'
        self.fields['pd_lifetime'].help_text = 'Lifetime probability of default'

        self.fields['pd_floor'].widget.attrs['class'] = 'form-control'
        self.fields['pd_floor'].widget.attrs['placeholder'] = '0.000100'
        self.fields['pd_floor'].label = 'PD Floor'
        self.fields['pd_floor'].help_text = 'Minimum PD floor for this segment'

        # LGD parameters
        self.fields['lgd_rate'].widget.attrs['class'] = 'form-control'
        self.fields['lgd_rate'].widget.attrs['placeholder'] = '45.00'
        self.fields['lgd_rate'].label = 'LGD Rate (%)'
        self.fields['lgd_rate'].help_text = 'Base loss given default rate'

        self.fields['lgd_floor'].widget.attrs['class'] = 'form-control'
        self.fields['lgd_floor'].widget.attrs['placeholder'] = '5.00'
        self.fields['lgd_floor'].label = 'LGD Floor (%)'

        self.fields['lgd_ceiling'].widget.attrs['class'] = 'form-control'
        self.fields['lgd_ceiling'].widget.attrs['placeholder'] = '90.00'
        self.fields['lgd_ceiling'].label = 'LGD Ceiling (%)'

        # Other parameters
        self.fields['ccf_rate'].widget.attrs['class'] = 'form-control'
        self.fields['ccf_rate'].widget.attrs['placeholder'] = '0.00'
        self.fields['ccf_rate'].label = 'CCF Rate (%)'
        self.fields['ccf_rate'].help_text = 'Credit conversion factor for undrawn commitments'

        self.fields['recovery_rate'].widget.attrs['class'] = 'form-control'
        self.fields['recovery_rate'].widget.attrs['placeholder'] = '0.00'
        self.fields['recovery_rate'].label = 'Recovery Rate (%)'

        self.fields['recovery_time_months'].widget.attrs['class'] = 'form-control'
        self.fields['recovery_time_months'].widget.attrs['placeholder'] = '36'
        self.fields['recovery_time_months'].label = 'Recovery Time (Months)'

        self.fields['discount_rate'].widget.attrs['class'] = 'form-control'
        self.fields['discount_rate'].widget.attrs['placeholder'] = '10.00'
        self.fields['discount_rate'].label = 'Discount Rate (%)'
        self.fields['discount_rate'].help_text = 'Rate for present value calculations'

        self.fields['macro_adjustment_factor'].widget.attrs['class'] = 'form-control'
        self.fields['macro_adjustment_factor'].widget.attrs['placeholder'] = '1.00'
        self.fields['macro_adjustment_factor'].label = 'Macro Adjustment Factor'
        self.fields['macro_adjustment_factor'].help_text = 'Macroeconomic adjustment multiplier'

        self.fields['forward_looking_adjustment'].widget.attrs['class'] = 'form-control'
        self.fields['forward_looking_adjustment'].widget.attrs['placeholder'] = '0.00'
        self.fields['forward_looking_adjustment'].label = 'Forward Looking Adjustment (%)'
        self.fields['forward_looking_adjustment'].help_text = 'Forward-looking adjustment percentage'

    def clean(self):
        cleaned_data = super().clean()
        pd_12m = cleaned_data.get('pd_12_month')
        pd_lifetime = cleaned_data.get('pd_lifetime')
        lgd_floor = cleaned_data.get('lgd_floor')
        lgd_ceiling = cleaned_data.get('lgd_ceiling')
        lgd_rate = cleaned_data.get('lgd_rate')

        if pd_12m and pd_lifetime and pd_12m > pd_lifetime:
            raise ValidationError('12-month PD cannot be greater than lifetime PD')

        if lgd_floor and lgd_ceiling and lgd_floor >= lgd_ceiling:
            raise ValidationError('LGD floor must be less than LGD ceiling')

        if lgd_rate and lgd_floor and lgd_ceiling:
            if lgd_rate < lgd_floor or lgd_rate > lgd_ceiling:
                raise ValidationError('LGD rate must be between floor and ceiling values')

        return cleaned_data


class DataUploadForm(forms.ModelForm):
    """Form for uploading data files to projects"""

    class Meta:
        model = DataUpload
        fields = ['upload_type', 'file_path']

        widgets = {
            'upload_type': forms.Select(attrs={'class': 'form-control'}),
            'file_path': forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.xlsx,.xls'})
        }

    def __init__(self, *args, **kwargs):
        super(DataUploadForm, self).__init__(*args, **kwargs)

        self.fields['upload_type'].label = 'Upload Type'
        self.fields['upload_type'].help_text = 'Select the type of data being uploaded'

        self.fields['file_path'].label = 'Data File'
        self.fields['file_path'].help_text = 'Upload CSV or Excel file (max 50MB)'

    def clean_file_path(self):
        file = self.cleaned_data['file_path']
        if file:
            # Check file size (50MB limit)
            if file.size > 50 * 1024 * 1024:
                raise ValidationError('File size must be less than 50MB')

            # Check file extension
            allowed_extensions = ['.csv', '.xlsx', '.xls']
            if not any(file.name.lower().endswith(ext) for ext in allowed_extensions):
                raise ValidationError('File must be CSV or Excel format')

        return file


class CompanyParametersUpdateForm(forms.ModelForm):
    """Form for updating company-level parameters after setup"""

    class Meta:
        model = Company
        fields = [
            'stage_1_threshold_days', 'stage_2_threshold_days', 'sicr_threshold_percent',
            'default_pd_floor', 'default_lgd_floor', 'default_lgd_ceiling'
        ]

        widgets = {
            'sicr_threshold_percent': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'default_pd_floor': forms.NumberInput(attrs={'step': '0.000001', 'min': '0'}),
            'default_lgd_floor': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'default_lgd_ceiling': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
        }

    def __init__(self, *args, **kwargs):
        super(CompanyParametersUpdateForm, self).__init__(*args, **kwargs)

        # Apply consistent styling
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        # Set labels and help text
        self.fields['stage_1_threshold_days'].label = 'Stage 1 Threshold (Days)'
        self.fields['stage_1_threshold_days'].help_text = 'Days past due before moving to Stage 2'

        self.fields['stage_2_threshold_days'].label = 'Stage 2 Threshold (Days)'
        self.fields['stage_2_threshold_days'].help_text = 'Days past due before moving to Stage 3'

        self.fields['sicr_threshold_percent'].label = 'SICR Threshold (%)'
        self.fields['sicr_threshold_percent'].help_text = 'Percentage increase in PD to trigger SICR'

        self.fields['default_pd_floor'].label = 'Default PD Floor'
        self.fields['default_pd_floor'].help_text = 'Minimum probability of default'

        self.fields['default_lgd_floor'].label = 'Default LGD Floor (%)'
        self.fields['default_lgd_floor'].help_text = 'Minimum loss given default percentage'

        self.fields['default_lgd_ceiling'].label = 'Default LGD Ceiling (%)'
        self.fields['default_lgd_ceiling'].help_text = 'Maximum loss given default percentage'


# Formset for bulk CBL Parameters entry
CBLParametersFormSet = forms.modelformset_factory(
    CBLParameters,
    form=CBLParametersForm,
    extra=1,
    can_delete=True
)

# Formset for bulk Branch Mappings entry
BranchMappingFormSet = forms.modelformset_factory(
    BranchMapping,
    form=BranchMappingForm,
    extra=1,
    can_delete=True
)