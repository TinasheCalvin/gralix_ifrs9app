from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from My_Users.models import MyUser


class Company(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=100, blank=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    created_by = models.ForeignKey('My_Users.MyUser', on_delete=models.CASCADE, related_name="company_creator", default=2)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Project(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=150, unique=True, blank=True)
    report_date = models.DateField()
    version = models.CharField(max_length=35)
    created_by = models.ForeignKey('My_Users.MyUser', on_delete=models.CASCADE, related_name="project_creator", default=2)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    last_modified_by = models.ForeignKey('My_Users.MyUser', on_delete=models.CASCADE, related_name="modifier", default=2)
    last_modified_on = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=[('Active', 'Active'), ('Locked', 'Locked')], default='Active')
    is_archived = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'report_date', 'version'], name="unique_version_per_company_and_date")
        ]

    def save(self):

        self.name = f"{self.company.name} - {self.report_date.strftime('%d %B %Y')} - {self.version}"

        if self.is_archived:
            self.status = 'Locked'
        else: 
            self.status = 'Active'
        return super(Project, self).save()

    def __str__(self):
        return self.name


class PDCalculationResult(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='pd_calculations')
    base_transition_matrix = models.JSONField(null=True, blank=True)
    stage_1_cumulative = models.JSONField(null=True, blank=True)
    stage_2_cumulative = models.JSONField(null=True, blank=True)
    stage_1_marginal = models.JSONField(null=True, blank=True)
    stage_2_marginal = models.JSONField(null=True, blank=True)
    cures = models.JSONField(null=True,blank=True)
    recoveries = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Calculation results for {self.project.name} on {self.created_at}"

class EADLGDCalculationResult(models.Model):
    account_no = models.CharField(max_length=50, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='ead_lgd_calculations')
    stage = models.CharField(max_length=10, null=True)
    loan_type = models.CharField(max_length=50, null=True)
    effective_interest_rate = models.FloatField(max_length=15, null=True)
    amortization_schedule = models.JSONField(null=True, blank=True)
    lgd_schedule = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"EAD and LGD results for account {self.account_no} in project {self.project.name}"
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account_no', 'project'], name='unique_account_per_project')
        ]


class ECLCalculationResult(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='ecl_calculations')
    ecl_results = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"ECL results for {self.project.name}"


class HistoricalCustomerLoanData(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pd_data')
    uploaded_file = models.JSONField(null=True, blank=True)
    file_name = models.CharField(max_length=100, null=True, blank=True)
    file_upload_date = models.DateTimeField(auto_now_add=True, null=True)
    is_valid = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Step 1: Mark all previous datasets for the same project as invalid when a new one is created
        if self.is_valid:
            HistoricalCustomerLoanData.objects.filter(project=self.project, is_valid=True).update(is_valid=False)

        # Step 2: Call the original save method to store the new file
        super(HistoricalCustomerLoanData, self).save(*args, **kwargs)

        # Step 3: Delete the oldest files if there are more than 5 datasets for this project
        data_files = HistoricalCustomerLoanData.objects.filter(project=self.project).order_by('file_upload_date')

        # If there are more than 5 data files per project, delete the oldest ones
        if data_files.count() > 5:
            excess_files = data_files[:-5]  # Get the oldest files beyond the 5 most recent
            for file_to_delete in excess_files:
                file_to_delete.delete()  # This deletes the object and its associated file if applicable

    def __str__(self) -> str:
        return f"{self.file_name} Uploaded on {self.file_upload_date}"

    
class CurrentLoanBook(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='current_loan_data')
    uploaded_file = models.JSONField(null=True, blank=True)
    file_name = models.CharField(max_length=100, null=True, blank=True)
    file_upload_date = models.DateTimeField(auto_now_add=True, null=True)
    is_valid = models.BooleanField(default=True)


    def save(self, *args, **kwargs):
        # Step 1: Mark all previous datasets for the same project as invalid when a new one is created
        if self.is_valid:
            CurrentLoanBook.objects.filter(project=self.project, is_valid=True).update(is_valid=False)

        # Step 2: Call the original save method to store the new file
        super(CurrentLoanBook, self).save(*args, **kwargs)

        # Step 3: Delete the oldest files if there are more than 5 datasets for this project
        data_files = CurrentLoanBook.objects.filter(project=self.project).order_by('file_upload_date')

        # If there are more than 5 data files per project, delete the oldest ones
        if data_files.count() > 5:
            excess_files = data_files[:-5]  # Get the oldest files beyond the 5 most recent
            for file_to_delete in excess_files:
                file_to_delete.delete()  # This deletes the object and its associated file if applicable

    def __str__(self) -> str:
        return f"{self.file_name} Uploaded on {self.file_upload_date}"

