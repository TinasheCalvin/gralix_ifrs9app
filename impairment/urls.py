from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='index'),
    path('company/<slug:company_slug>/projects/', views.project_selection, name='company_projects'),
    path('company/<slug:company_slug>/project/<int:pk>/data-source/', views.data_source, name='data_source'),
    path('company/<slug:company_slug>/project/<int:pk>/upload_historical/', views.upload_historical_loan_data, name='upload_historical_loan_data'),
    path('company/<slug:company_slug>/project/<int:pk>/upload_current/', views.upload_current_loan_book, name='upload_current_loan_book'),
    path('company/<slug:company_slug>/project/<int:pk>/dashboard/', views.dashboard, name='dashboard'),
    path('company/<slug:company_slug>/project/<int:pk>/cumulative-probability-of-default/', views.cumulative_probability_of_default, name='cumulative_probability_of_default'),
    path('company/<slug:company_slug>/project/<int:pk>/marginal-probability-of-default/', views.marginal_probability_of_default, name='marginal_probability_of_default'),
    path('company/<slug:company_slug>/project/<int:pk>/probability-of-cure-or-recovery/', views.cures_and_recoveries, name='probability_cures_and_recoveries'),
    path('company/<slug:company_slug>/project/<int:pk>/current-loan-book-stage-1/', views.current_stage_1, name='current_stage_1'),
    path('company/<slug:company_slug>/project/<int:pk>/current-loan-book-stage-2/', views.current_stage_2, name='current_stage_2'),
    path('company/<slug:company_slug>/project/<int:pk>/current-loan-book-stage-3/', views.current_stage_3, name='current_stage_3'),
    path('company/<slug:company_slug>/project/<int:pk>/lgd-analysis/', views.lgd_analysis, name='lgd_analysis'),
    path('company/<slug:company_slug>/project/<int:pk>/ead-analysis/', views.ead_analysis, name='ead_analysis'),
    path('company/<slug:company_slug>/project/<int:pk>/forward-looking-information/', views.fli, name='forward_looking_information'),

    # New paths for ECL calculation and display
    path('company/<slug:company_slug>/project/<int:pk>/fetch-ecl/', views.fetch_ecl, name='fetch_ecl'),
    path('company/<slug:company_slug>/project/<int:pk>/calculate-ecl/', views.calculate_ECL, name='calculate_ecl'),

    # Authentication and Company/Project management paths
    path('sign_in/', views.sign_in, name='sign_in'),
    path('sign-out/', views.sign_out, name='sign_out'),
    path('sign-up/', views.sign_up, name='sign_up'),
    path('add-company/', views.create_company, name='create_company'),
    path('company/<slug:company_slug>/create-project/', views.create_project, name='create_project'),
]

