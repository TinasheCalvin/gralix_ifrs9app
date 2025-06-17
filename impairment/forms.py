from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Project, Company


class SignUpForm(UserCreationForm):

    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))


    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')


    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['placeholder'] = 'Password'
        self.fields['password1'].label = ''
        self.fields['password1'].help_text = '<ul class="form-text text-muted small"><li>Your password can\'t be too similar to your other personal information.</li><li>Your password must contain at least 8 characters.</li><li>Your password can\'t be a commonly used password.</li><li>Your password can\'t be entirely numeric.</li></ul>'

        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm Password'
        self.fields['password2'].label = ''
        # self.fields['password2'].help_text = '<p class="form-text text-muted small">Enter the same password as before, for verification.</p>'

    def save(self, commit=True):
        user = super(SignUpForm, self).save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.username = f"{user.first_name}_{user.last_name}"

        # Check if the generated username already exists
        if User.objects.filter(username=user.username).exists():
            user.username = f"{user.username}_{User.objects.count()}"
        
        if commit:
            user.save()
        return user

class DateInput(forms.DateInput):
    input_type = 'date'


class CompanyForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = ['name', 'description']
    
    def __init__(self, *args, **kwargs):
        super(CompanyForm, self).__init__(*args, **kwargs)
        
        self.fields['name'].widget.attrs['class'] = 'form-control'
        self.fields['name'].widget.attrs['placeholder'] = 'Type Company Name'
        self.fields['name'].label = ''
        
        self.fields['description'].widget.attrs['class'] = 'form-control'
        self.fields['description'].widget.attrs['placeholder'] = 'Enter your project descrtiption (255 Character Limit)'
        self.fields['description'].help_text = ""
        self.fields['description'].label = ''


class ProjectForm(forms.ModelForm):

    class Meta:
        model = Project
        fields = ['version', 'report_date']

        widgets = {
            'report_date': forms.DateInput(
                format=('%Y-%m-%d'),
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Select Report Date',
                    'type': 'date'
                }
            )
        }
    
    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        
        self.fields['version'].widget.attrs['class'] = 'form-control'
        self.fields['version'].widget.attrs['placeholder'] = 'Enter Project Version'
        self.fields['version'].label = ''
        
        # self.fields['description'].widget.attrs['class'] = 'form-control'
        # self.fields['description'].widget.attrs['placeholder'] = 'Enter your project descrtiption (255 Character Limit)'
        # self.fields['description'].help_text = ""
        # self.fields['description'].label = ''

        self.fields['report_date'].widget.attrs['class'] = 'form-control'
        self.fields['report_date'].widget.attrs['placeholder'] = 'Select Report Date'
        self.fields['report_date'].label = 'Select Report Date '


class HistoricalLoanDataForm(forms.Form):
    historical_form = forms.FileField(disabled=False)


class CurrentLoanBookForm(forms.Form):
    current_loan_data_form = forms.FileField(disabled=True) 

