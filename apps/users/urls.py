"""
URL configuration for users app.

This module defines URL patterns for user-related views including
authentication, registration, profile management, and doctor search.
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    
    # Dashboard and Profile
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('profile/', views.ProfileUpdateView.as_view(), name='profile'),
    path('delete-account/', views.DeleteAccountView.as_view(), name='delete_account'),
    path('profile-image/<int:user_id>/', views.serve_patient_profile_image, name='profile_image'),
    path('smart-checkup/', views.smart_checkup_view, name='smart_checkup'),
    
    # Doctor Search and Booking
    path('doctors/', views.DoctorSearchView.as_view(), name='search_doctors'),
    path('book-appointment/<int:doctor_id>/', views.BookAppointmentView.as_view(), name='book_appointment'),
    path('cancel-appointment/<int:appointment_id>/', views.CancelAppointmentView.as_view(), name='cancel_appointment'),
    path('my-appointments/', views.MyAppointmentsView.as_view(), name='my_appointments'),
    
    # API endpoints for appointments
    path('api/appointments/<int:appointment_id>/details/', views.AppointmentDetailsAPI.as_view(), name='appointment_details'),
    path('api/appointments/<int:appointment_id>/review/', views.SubmitReviewAPI.as_view(), name='submit_review'),
    
    # Password Management
    path('password-change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='users/password_change.html',
             success_url='/users/password-change-done/'
         ), 
         name='password_change'),
    path('password-change-done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='users/password_change_done.html'
         ),
         name='password_change_done'),
    
    # Password Reset
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             success_url='/users/password-reset-done/'
         ),
         name='password_reset'),
    path('password-reset-done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/users/password-reset-complete/'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]
