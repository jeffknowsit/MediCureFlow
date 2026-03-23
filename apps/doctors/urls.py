"""
URL configuration for doctors app.

This module defines URL patterns for doctor-related views including
registration, authentication, dashboard, appointments, and profile management.
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'doctors'

urlpatterns = [
    # Doctor Authentication
    path('register/', views.DoctorRegistrationView.as_view(), name='register'),
    path('logout/', views.DoctorLogoutView.as_view(), name='logout'),
    
    # Doctor Dashboard and Profile
    path('dashboard/', views.DoctorDashboardView.as_view(), name='dashboard'),
    path('profile/', views.DoctorProfileView.as_view(), name='profile'),
    path('profile-image/<int:doctor_id>/', views.serve_doctor_profile_image, name='profile_image'),
    path('analytics/', views.DoctorAnalyticsView.as_view(), name='analytics'),
    
    # Appointment Management
    path('appointments/', views.DoctorAppointmentsView.as_view(), name='appointments'),
    path('appointments/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('appointments/<int:pk>/update/', views.AppointmentUpdateView.as_view(), name='appointment_update'),
    
    # Availability Management
    path('availability/', views.DoctorAvailabilityView.as_view(), name='availability'),
    path('availability/add/', views.AddAvailabilityView.as_view(), name='add_availability'),
    path('api/availability/add/', views.AddAvailabilityAjaxView.as_view(), name='add_availability_ajax'),
    path('api/availability/<int:slot_id>/delete/', views.DeleteAvailabilityView.as_view(), name='delete_availability'),
    path('api/availability/<int:slot_id>/update/', views.UpdateAvailabilityView.as_view(), name='update_availability'),
    path('api/toggle-availability/', views.ToggleAvailabilityView.as_view(), name='toggle_availability'),
    
    # Doctor Search (redirect to main search)
    path('search/', views.DoctorSearchRedirectView.as_view(), name='search'),
    
    # API endpoints for AJAX requests
    path('api/appointments/<int:appointment_id>/update-status/', 
         views.AppointmentStatusUpdateAPI.as_view(), 
         name='appointment_status_update_api'),
    path('api/appointments/<int:appointment_id>/complete/', 
         views.AppointmentCompleteAPI.as_view(), 
         name='appointment_complete_api'),
    path('api/appointments/<int:appointment_id>/update-notes/', 
         views.AppointmentNotesUpdateAPI.as_view(), 
         name='appointment_notes_update_api'),
    path('api/appointments/<int:appointment_id>/consultation-save/', 
         views.AppointmentConsultationAPI.as_view(), 
         name='appointment_consultation_save_api'),
    path('api/patient/<int:patient_id>/history/', 
         views.PatientHistoryAPI.as_view(), 
         name='patient_history_api'),
    path('api/available-slots/', 
         views.DoctorAvailableSlotsView.as_view(), 
         name='available_slots_api'),
    
    # Public Doctor Detail
    path('<int:pk>/', views.DoctorDetailView.as_view(), name='detail'),
    
    # Password Management for Doctors
    path('password-change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='doctors/password_change.html',
             success_url='/doctors/password-change-done/'
         ), 
         name='password_change'),
    path('password-change-done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='doctors/password_change_done.html'
         ),
         name='password_change_done'),
]
