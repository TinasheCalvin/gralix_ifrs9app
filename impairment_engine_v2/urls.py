from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="index"),
    path("add-company/", views.create_company, name="create_company"),
    path("company/branches/download", views.download_branch_mappings_template, name="download_branch_mappings"),
    path("company/<slug:company_slug>/branches", views.upload_branch_mappings, name="upload_branch_mappings"),
    path("company/<slug:company_slug>/factors", views.upload_risk_factors, name="upload_risk_factors"),
    path("lgd/factors/download", views.download_risk_factors_template, name="download_risk_factors"),
    path("company/<slug:company_slug>/risks", views.configure_risk_factors, name="configure_risk_factors"),
    path("company/<slug:company_slug>/factors/<int:factor_id>/add", views.add_risk_factor_value, name="add_risk_factor_value"),
    path("company/<slug:company_slug>/projects/", views.company_projects, name="company_projects"),
    path("company/<slug:company_slug>/add-project", views.create_project, name="create_project"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/upload/", views.data_upload_wizard, name="upload_wizard"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/upload/sheets/", views.process_sheet_selection, name="process_sheets"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/upload/mapping/", views.process_column_mapping, name="process_mapping"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/upload/finalize/", views.finalize_data_upload_v2, name="finalize_upload"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/lgd/calculate", views.compute_project_lgd, name="compute_project_lgd"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/pd/calculate", views.compute_project_pd, name="compute_project_pd"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/ecl/calculate", views.compute_project_ecl, name="compute_project_ecl"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/cbl", views.current_cbl, name="current_cbl"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/ead", views.current_exposure, name="current_exposure"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/lgd", views.current_loss_given_default, name="current_loss_given_default"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/pd", views.current_probability_of_default, name="current_probability_of_default"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/lifetime_pd", views.lifetime_probability_of_default, name="lifetime_probability_of_default"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/<slug:stage>", views.current_loanbook, name="current_loan_book"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/ecl/<slug:stage>", views.expected_credit_loss, name="expected_credit_loss"),
    path("company/<slug:company_slug>/projects/<slug:project_slug>/dashboard", views.dashboard, name="project_dashboard"),
]

