"""MediCureFlow URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.users import views as users_views
from apps.doctors import views as doctors_views

admin.site.site_header = "MediCureFlow Admin Portal"
admin.site.site_title = "MediCureFlow Admin"
admin.site.index_title = "Welcome to MediCureFlow Administration"

urlpatterns = [
    path('', users_views.HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    
    # App URLs with namespacing
    path('users/', include('apps.users.urls')),
    path('doctors/', include('apps.doctors.urls')),
    path('payments/', include('apps.payments.urls')),
    # path('quick-checkup/', include('apps.health_ai.urls')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    
    # Powerful Admin System
    path('admin-system/', include('apps.admin_system.urls', namespace='admin_system')),
    
    # Backward compatibility redirects
    path('login/', users_views.CustomLoginView.as_view(), name='login'),
    path('register/', users_views.UserRegistrationView.as_view(), name='register'),
    # MAIN DASHBOARD URL - THIS IS WHAT'S BEING USED!
    path('dashboard/', users_views.DashboardView.as_view(), name='dashboard'),
    path('search/', users_views.DoctorSearchView.as_view(), name='search_doctors'),
    path('profile/', users_views.ProfileUpdateView.as_view(), name='profile'),
    path('change_password/', users_views.home_view, name='change_password'),
    path('logout/', users_views.CustomLogoutView.as_view(), name='logout'),
    
    # Doctor backward compatibility - redirect to proper doctor app URLs
    path('doctor_register/', doctors_views.doctor_registration_view, name='doctor_register'),
    path('doctor_login/', doctors_views.doctor_login_view, name='doctor_login'),
    path('doctor_appointments/', doctors_views.doctor_appointments_view, name='doctor_appointments'),
    path('doctor_profile/', doctors_views.doctor_profile_view, name='doctor_profile'),
    path('doctor_logout/', doctors_views.doctor_logout_view, name='doctor_logout'),
    path('change-password/', doctors_views.doctor_change_password_view, name='change_password'),
    
    # Legal and Support Pages
    path('privacy-policy/', users_views.privacy_policy_view, name='privacy_policy'),
    path('terms-of-service/', users_views.terms_of_service_view, name='terms_of_service'),
    path('help-center/', users_views.help_center_view, name='help_center'),
    path('about/', users_views.about_us_view, name='about_us'),
    
    # API URLs
    path('api/', include('api_urls', namespace='api')),
    path('api-auth/', include('rest_framework.urls')),
]

# Add debug toolbar URLs for development
# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         path('__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns

# Static and media files
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
