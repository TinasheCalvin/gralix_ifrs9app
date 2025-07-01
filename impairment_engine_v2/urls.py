from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='index'),
    path('add-company/', views.create_company, name='create_company'),
    path('company/<slug:company_slug>/projects/', views.company_projects, name='company_projects'),
    path('company/<slug:company_slug>/add-project', views.create_project, name='create_project'),
    path('company/<slug:company_slug>/projects/<slug:project_slug>/upload/', views.data_upload_wizard, name='upload_wizard'),
    path('company/<slug:company_slug>/projects/<slug:project_slug>/upload/sheets/', views.process_sheet_selection, name='process_sheets'),
    path('company/<slug:company_slug>/projects/<slug:project_slug>/upload/mapping/', views.process_column_mapping, name='process_mapping'),
    path('company/<slug:company_slug>/projects/<slug:project_slug>/upload/finalize/', views.finalize_data_upload_v2, name='finalize_upload'),
    path('company/<slug:company_slug>/projects/<slug:project_slug>/loanbook/<slug:stage>', views.current_loanbook, name='current_loan_book'),
    path('company/<slug:company_slug>/projects/<slug:project_slug>/dashboard', views.dashboard, name='project_dashboard'),
]

