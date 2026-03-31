"""
Modern views for users app.

This module contains class-based and function-based views for user management,
authentication, doctor search, and appointment booking.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, FormView, View
)
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from django.db import transaction
from apps.doctors.models import Doctor, Appointment, Review
from .models import UserProfile
from .forms import (
    CustomUserRegistrationForm, CustomAuthenticationForm,
    UserProfileForm, UserUpdateForm, DoctorSearchForm
)
from apps.doctors.forms import AppointmentForm
import logging

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    """
    Home page view with doctor search functionality.
    """
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DoctorSearchForm()
        context['featured_doctors'] = Doctor.objects.filter(is_available=True)[:6]
        context['specialties'] = Doctor.SPECIALTIES
        
        # Currency info for templates (consistent with admin and search)
        from django.conf import settings
        currency = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
        currency_symbols = getattr(settings, 'CURRENCY_SYMBOLS', {
            'USD': '$',
            'INR': '₹',
            'EUR': '€',
            'GBP': '£'
        })
        context['current_currency'] = currency
        context['currency_symbol'] = currency_symbols.get(currency, '$')
        
        return context


class CustomLoginView(LoginView):
    """
    Custom login view using our authentication form.
    """
    form_class = CustomAuthenticationForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        # Smart redirection based on user type
        user = self.request.user
        if hasattr(user, 'doctor_profile'):
            return reverse_lazy('doctors:dashboard')
        elif user.is_staff:
            return reverse_lazy('admin_system:dashboard')
        else:
            return reverse_lazy('users:dashboard')
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username or password.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """
    Custom logout view with proper session management.
    """
    next_page = reverse_lazy('home')
    http_method_names = ['get', 'post']
    
    def post(self, request, *args, **kwargs):
        messages.success(request, 'You have been successfully logged out.')
        return super().post(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        # If accessed via GET, show confirmation page
        return render(request, 'users/logout_confirm.html')


class UserRegistrationView(CreateView):
    """
    User registration view.
    """
    form_class = CustomUserRegistrationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            'Registration successful! You can now log in with your credentials.'
        )
        logger.info(f'New user registered: {form.cleaned_data["username"]}')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Smart dashboard view that redirects users to appropriate dashboards.
    """
    template_name = 'users/dashboard.html'
    login_url = reverse_lazy('login')
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a doctor and redirect to doctor dashboard
        if hasattr(request.user, 'doctor_profile'):
            return redirect('doctors:dashboard')
        # Check if user is admin staff and redirect to admin dashboard
        elif request.user.is_staff:
            return redirect('admin_system:dashboard')
        # Otherwise proceed with patient dashboard
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user profile or create if doesn't exist
        profile, created = UserProfile.objects.get_or_create(user=user)
        context['profile'] = profile
        
        # Import and use analytics
        from .analytics import PatientAnalytics
        analytics = PatientAnalytics(user)
        
        # Get comprehensive dashboard statistics
        context.update({
            'dashboard_stats': analytics.get_dashboard_stats(),
            'appointment_trends': analytics.get_appointment_trends(),
            'specialty_breakdown': analytics.get_specialty_breakdown(),
            'recent_activity': analytics.get_recent_activity(),
            'health_insights': analytics.get_health_insights(),
        })
        
        # Get recent appointments with more details
        context['recent_appointments'] = Appointment.objects.filter(
            patient=user
        ).select_related('doctor').order_by('-created_at')[:5]
        
        # Upcoming appointments count
        from django.utils import timezone as tz
        today = tz.now().date()
        context['upcoming_appointments'] = Appointment.objects.filter(
            patient=user, appointment_date__gte=today,
            status__in=['scheduled', 'confirmed']
        ).count()
        
        # Available doctors count
        context['available_doctors_count'] = Doctor.objects.filter(
            is_available=True, is_on_duty=True
        ).count()
        
        # Get notifications
        from apps.notifications.models import Notification
        context['notifications'] = Notification.objects.filter(
            recipient=user,
            read_at__isnull=True
        ).order_by('-created_at')[:10]
        
        # Get recommended doctors (same city as user or highly rated)
        if profile.city:
            context['recommended_doctors'] = Doctor.objects.filter(
                city__icontains=profile.city, is_available=True
            ).order_by('-average_rating')[:4]
        else:
            context['recommended_doctors'] = Doctor.objects.filter(
                is_available=True
            ).order_by('-average_rating')[:4]
        
        # Convert chart data to JSON for JavaScript
        import json
        context['appointment_trends_json'] = json.dumps(context['appointment_trends'])
        context['specialty_breakdown_json'] = json.dumps(context['specialty_breakdown'])
        
        return context


class DoctorSearchView(ListView):
    """
    Advanced doctor search and listing view with comprehensive filtering.
    """
    model = Doctor
    template_name = 'users/search_doctors.html'
    context_object_name = 'doctors'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Doctor.objects.filter(is_available=True).select_related('user')
        
        # Get all search parameters
        specialty = self.request.GET.get('specialty')
        city = self.request.GET.get('city')
        state = self.request.GET.get('state')
        search_query = self.request.GET.get('search_query')
        min_experience = self.request.GET.get('min_experience')
        max_fee = self.request.GET.get('max_fee')
        rating_min = self.request.GET.get('rating_min')
        language = self.request.GET.get('language')
        verified_only = self.request.GET.get('verified_only')
        availability_day = self.request.GET.get('availability_day')
        sort_by = self.request.GET.get('sort_by', 'relevance')
        
        # Apply specialty filter
        if specialty:
            queryset = queryset.filter(specialty=specialty)
            
        # Apply location filters
        if city:
            queryset = queryset.filter(city__icontains=city)
        if state:
            queryset = queryset.filter(state__icontains=state)
            
        # Apply text search
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(qualification__icontains=search_query) |
                Q(bio__icontains=search_query) |
                Q(clinic_name__icontains=search_query) |
                Q(hospital_affiliations__icontains=search_query) |
                Q(specializations__name__icontains=search_query)
            ).distinct()
            
        # Apply experience filter
        if min_experience:
            try:
                min_exp = int(min_experience)
                queryset = queryset.filter(experience_years__gte=min_exp)
            except ValueError:
                pass
                
        # Apply fee filter
        if max_fee:
            try:
                max_fee_val = float(max_fee)
                queryset = queryset.filter(consultation_fee__lte=max_fee_val)
            except ValueError:
                pass
                
        # Apply rating filter
        if rating_min:
            try:
                min_rating = float(rating_min)
                queryset = queryset.filter(average_rating__gte=min_rating)
            except ValueError:
                pass
                
        # Apply language filter
        if language:
            queryset = queryset.filter(languages_spoken__icontains=language)
            
        # Apply verification filter
        if verified_only:
            queryset = queryset.filter(is_verified=True)
            
        # Apply availability day filter
        if availability_day:
            try:
                day_num = int(availability_day)
                queryset = queryset.filter(
                    availability_slots__day_of_week=day_num,
                    availability_slots__is_active=True
                ).distinct()
            except ValueError:
                pass
        
        # Apply sorting
        if sort_by == 'rating':
            queryset = queryset.order_by('-average_rating', '-total_reviews')
        elif sort_by == 'experience':
            queryset = queryset.order_by('-experience_years')
        elif sort_by == 'fee_low':
            queryset = queryset.order_by('consultation_fee')
        elif sort_by == 'fee_high':
            queryset = queryset.order_by('-consultation_fee')
        elif sort_by == 'reviews':
            queryset = queryset.order_by('-total_reviews')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'name':
            queryset = queryset.order_by('first_name', 'last_name')
        else:  # relevance (default)
            if search_query:
                # Prioritize doctors with better ratings when searching
                queryset = queryset.order_by('-average_rating', '-total_reviews')
            else:
                queryset = queryset.order_by('-average_rating', '-total_reviews')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DoctorSearchForm(self.request.GET)
        context['total_doctors'] = self.get_queryset().count()
        
        # Add filter context for the template
        context['current_filters'] = {
            'specialty': self.request.GET.get('specialty', ''),
            'city': self.request.GET.get('city', ''),
            'state': self.request.GET.get('state', ''),
            'search_query': self.request.GET.get('search_query', ''),
            'min_experience': self.request.GET.get('min_experience', ''),
            'max_fee': self.request.GET.get('max_fee', ''),
            'rating_min': self.request.GET.get('rating_min', ''),
            'language': self.request.GET.get('language', ''),
            'verified_only': self.request.GET.get('verified_only', ''),
            'availability_day': self.request.GET.get('availability_day', ''),
            'sort_by': self.request.GET.get('sort_by', 'relevance'),
        }
        
        # Add choices for filters
        context['specialties'] = Doctor.SPECIALTIES
        context['languages'] = ['English', 'Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi', 'Gujarati']
        context['days_of_week'] = [
            (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
            (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
        ]
        
        # Add available cities and states for filter dropdowns
        all_doctors = Doctor.objects.filter(is_available=True)
        context['available_cities'] = list(all_doctors.values_list('city', flat=True).distinct().order_by('city'))
        context['available_states'] = list(all_doctors.values_list('state', flat=True).distinct().order_by('state'))
        
        # Currency info for templates (kept in sync with admin)
        from django.conf import settings
        currency = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
        currency_symbols = getattr(settings, 'CURRENCY_SYMBOLS', {
            'USD': '$',
            'INR': '₹',
            'EUR': '€',
            'GBP': '£'
        })
        context['current_currency'] = currency
        context['currency_symbol'] = currency_symbols.get(currency, '$')
        
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """
    User profile update view.
    """
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('profile')
    login_url = reverse_lazy('login')
    
    def get_object(self, queryset=None):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_form'] = UserUpdateForm(instance=self.request.user)
        return context
    
    def form_valid(self, form):
        # Use database transaction to ensure both forms save atomically
        try:
            with transaction.atomic():
                # Save the profile first
                profile = form.save()
                
                # Handle user form if provided
                user_form = UserUpdateForm(
                    self.request.POST, instance=self.request.user
                )
                if user_form.is_valid():
                    user_form.save()
                else:
                    # Log validation errors but don't fail the whole transaction
                    logger.warning(f'User form validation failed for user {self.request.user.username}: {user_form.errors}')
                
                logger.info(f'Profile successfully updated for user: {self.request.user.username}')
                messages.success(self.request, 'Profile updated successfully!')
                
        except Exception as e:
            logger.error(f'Error updating profile for user {self.request.user.username}: {e}')
            messages.error(self.request, 'An error occurred while updating your profile. Please try again.')
            return self.form_invalid(form)
        
        return redirect(self.success_url)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class BookAppointmentView(LoginRequiredMixin, CreateView):
    """
    Appointment booking view - PATIENTS ONLY.
    Doctors and admin cannot book appointments.
    """
    model = Appointment
    form_class = AppointmentForm
    template_name = 'users/book_appointment.html'
    login_url = reverse_lazy('login')
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure only patients can book appointments
        # Doctors and administrators cannot book appointments
        if request.user.is_authenticated:
            if request.user.is_staff or hasattr(request.user, 'doctor_profile'):
                messages.error(request, 'Only patients can book appointments. Doctors and administrators are restricted from booking.')
                if hasattr(request.user, 'doctor_profile'):
                    return redirect('doctors:dashboard')
                return redirect('admin_system:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor_id = self.kwargs.get('doctor_id')
        context['doctor'] = get_object_or_404(Doctor, id=doctor_id)
        return context
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Set doctor on instance before validation
        doctor_id = self.kwargs.get('doctor_id')
        if doctor_id:
            form.instance.doctor = get_object_or_404(Doctor, id=doctor_id)
        return form
    
    def form_valid(self, form):
        appointment = form.save(commit=False)
        # Doctor is already set in get_form
        appointment.patient = self.request.user
        appointment.patient_email = self.request.user.email
        
        # Inject AI Summary if present
        ai_brief = self.request.session.pop('ai_doctor_brief', None)
        if ai_brief:
            border = "=" * 30
            ai_notes = f"\n\n{border}\n🏥 AI DIAGNOSTIC REPORT\n{border}\n\n"
            ai_notes += f"SUMMARY: {ai_brief.get('summary', '')}\n\n"
            diagnoses = ai_brief.get('possible_diagnoses', [])
            ai_notes += f"PROBABLE CONDITIONS:\n- " + "\n- ".join(diagnoses) + "\n\n"
            tests = ai_brief.get('suggested_tests', [])
            ai_notes += f"SUGGESTED TESTS:\n- " + "\n- ".join(tests) + "\n\n"
            ai_notes += f"RED FLAGS:\n{ai_brief.get('red_flags', '')}\n"
            
            # Prepend or append
            if appointment.patient_notes:
                appointment.patient_notes = appointment.patient_notes + ai_notes
            else:
                appointment.patient_notes = ai_notes
        
        # Get user profile for contact info
        try:
            profile = self.request.user.profile
            appointment.patient_phone = profile.phone
        except UserProfile.DoesNotExist:
            pass
        
        appointment.save()
        
        messages.success(
            self.request,
            f'Appointment booked successfully with {appointment.doctor.display_name}!'
        )
        logger.info(f'Appointment booked: {appointment.id} by user {self.request.user.username}')
        
        return redirect('payments:create', appointment_id=appointment.id)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class MyAppointmentsView(LoginRequiredMixin, ListView):
    """
    View for user's appointments - PATIENTS ONLY.
    Doctors and admin should use their own dashboards.
    """
    model = Appointment
    template_name = 'users/my_appointments.html'
    context_object_name = 'appointments'
    login_url = reverse_lazy('login')
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure only patients can view their appointments
        if request.user.is_authenticated and request.user.is_staff:
            messages.error(request, 'Please use the admin system or doctor dashboard to manage appointments.')
            if request.user.is_staff:
                return redirect('admin_system:appointment_management')
            return redirect('doctors:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Appointment.objects.filter(
            patient=self.request.user
        ).order_by('-appointment_date', '-appointment_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointments = context['appointments']
        
        # Calculate unique doctors count
        unique_doctors = set()
        for appointment in appointments:
            unique_doctors.add(appointment.doctor_id)
        context['unique_doctors_count'] = len(unique_doctors)
        
        return context

class CancelAppointmentView(LoginRequiredMixin, View):
    """
    View for users to cancel their own appointments.
    """
    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
        
        # Only allow cancellation for scheduled or confirmed appointments
        if appointment.status in ['scheduled', 'confirmed']:
            appointment.status = 'cancelled'
            appointment.save(skip_validation=True)
            messages.success(request, f'Appointment with {appointment.doctor.display_name} has been cancelled.')
            logger.info(f'Appointment {appointment_id} cancelled by user {request.user.username}')
        else:
            messages.warning(request, f'This appointment cannot be cancelled as it is already {appointment.get_status_display()}.')
            
        return redirect(request.META.get('HTTP_REFERER', 'users:dashboard'))


# Keep one function-based view for the home page fallback
def home_view(request):
    """Simple home view for URL compatibility."""
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    else:
        return redirect('search_doctors')  # This will use the main URL pattern


# Legal and Support Pages
def privacy_policy_view(request):
    """Privacy Policy page view."""
    return render(request, 'legal/privacy_policy.html')


def terms_of_service_view(request):
    """Terms of Service page view."""
    return render(request, 'legal/terms_of_service.html')


def help_center_view(request):
    """Help Center page view."""
    return render(request, 'support/help_center.html')


def about_us_view(request):
    """About Us page view."""
    return render(request, 'pages/about_us.html')

def serve_patient_profile_image(request, user_id):
    """Serve the profile picture from SQLite binary storage."""
    user_profile = get_object_or_404(UserProfile, user__id=user_id)
    if user_profile.profile_picture_blob and user_profile.profile_picture_mime:
        return HttpResponse(user_profile.profile_picture_blob, content_type=user_profile.profile_picture_mime)
    raise Http404("Profile picture not found")


class SubmitReviewAPI(LoginRequiredMixin, View):
    """
    API view to submit a doctor review for a completed appointment.
    """
    http_method_names = ['post']
    
    def post(self, request, appointment_id):
        try:
            import json
            from django.http import JsonResponse
            
            data = json.loads(request.body)
            rating = int(data.get('rating', 0))
            comment = data.get('comment', '')
            
            if not (1 <= rating <= 5):
                return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5 stars.'})
                
            # Get appointment and ensure it belongs to the patient
            appointment = get_object_or_404(
                Appointment, 
                id=appointment_id, 
                patient=request.user,
                status='completed'
            )
            
            # Double check for existing reviews between this doctor and patient for this appointment
            # (OneToOneField already handles this, but explicit check is good for custom error)
            if hasattr(appointment, 'review'):
                return JsonResponse({
                    'success': False, 
                    'message': f'You have already submitted a review for this visit with {appointment.doctor.display_name}.'
                })
                
            # Create review
            review = Review.objects.create(
                doctor=appointment.doctor,
                patient=request.user,
                appointment=appointment,
                rating=rating,
                comment=comment,
                is_approved=True 
            )
            
            # Update doctor statistics
            appointment.doctor.update_statistics()
            
            logger.info(f'Review {review.id} submitted for doctor {appointment.doctor.id} by user {request.user.username}')
            
            return JsonResponse({
                'success': True, 
                'message': 'Review submitted successfully! Thank you for your feedback.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data format.'})
        except Appointment.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Completed appointment record not found.'})
        except Exception as e:
            error_msg = str(e)
            logger.error(f'Error submitting review for appointment {appointment_id}: {error_msg}')
            
            if "UNIQUE constraint failed" in error_msg:
                return JsonResponse({
                    'success': False, 
                    'message': 'A review for this doctor-patient visit already exists.'
                })
                
            return JsonResponse({
                'success': False, 
                'message': 'A system error occurred while processing your review. Please try again later.'
            })


class AppointmentDetailsAPI(LoginRequiredMixin, View):
    """
    API view to fetch detailed remarks and prescription for a completed appointment.
    """
    def get(self, request, appointment_id):
        from django.http import JsonResponse
        try:
            appointment = get_object_or_404(
                Appointment, 
                id=appointment_id, 
                patient=request.user
            )
            
            # Prepare referral info
            referral = None
            if appointment.recommended_doctor:
                doc = appointment.recommended_doctor
                referral = {
                    'name': doc.display_name,
                    'specialty': doc.get_specialty_display(),
                    'id': doc.id
                }
                
            medicines = []
            for med in appointment.medications.all():
                medicines.append({
                    'name': med.name,
                    'amount': med.amount,
                    'dosage': med.dosage,
                    'eating_quantity': med.eating_quantity,
                    'notes': med.notes
                })
                
            reports = []
            for report in appointment.test_reports.all():
                reports.append({
                    'name': report.test_name,
                    'url': report.report_file.url if report.report_file else None
                })
                
            data = {
                'doctor_name': appointment.doctor.display_name,
                'date': appointment.appointment_date.strftime('%d %b, %Y'),
                'time': appointment.appointment_time.strftime('%I:%M %p'),
                'remarks': appointment.consultation_remarks or 'No clinical remarks provided by the doctor.',
                'medicines': medicines,
                'reports': reports,
                'next_date': appointment.next_appointment_date.strftime('%d %b, %Y') if appointment.next_appointment_date else None,
                'next_time': appointment.next_appointment_time.strftime('%I:%M %p') if appointment.next_appointment_time else None,
                'referral': referral
            }
            
            return JsonResponse({'success': True, 'details': data})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class DeleteAccountView(LoginRequiredMixin, View):
    """
    View for users to delete their own account.
    Restricted: Staff/Admins cannot delete their accounts this way.
    """
    def post(self, request):
        user = request.user
        
        # Security: Do not allow staff or superusers to delete themselves via this view
        if user.is_staff or user.is_superuser:
            messages.error(request, 'Administrative accounts cannot be deleted through this interface. Please contact system management.')
            return redirect('users:profile')
            
        try:
            with transaction.atomic():
                # Store username for the message
                username = user.username
                # Log the deletion
                logger.info(f'User {username} deleted their account.')
                # Delete the user (this will cascade delete the profile if setup correctly)
                user.delete()
                
            messages.success(request, 'Your account has been permanently deleted. We are sorry to see you go.')
            return redirect('home')
        except Exception as e:
            logger.error(f'Error deleting account for {user.username}: {e}')
            messages.error(request, 'An error occurred while deleting your account.')
            return redirect('users:profile')


import google.generativeai as genai
import os, json
from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.doctors.models import Doctor

@login_required
def smart_checkup_view(request):
    """
    AI Diagnostic Assistant using Gemini 3.1 Flash Lite.
    Provides Patient recommendations, a structured Doctor's brief, and
    queries the database to recommend an appropriate Doctor based on symptoms.
    """
    if request.method == "POST":
        symptoms = request.POST.get('symptoms', '')
        duration = request.POST.get('duration', 'Not specified')
        severity = request.POST.get('severity', 'Not specified')
        history = request.POST.get('history', 'None')

        try:
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get("GEMINI_API_KEY", "")

            if not api_key:
                return render(request, 'users/smart_checkup/result.html', {
                    'data': None,
                    'error': 'Gemini API Key is missing. Please configure GEMINI_API_KEY in your .env file.'
                })

            genai.configure(api_key=api_key)
            # Use Gemini Flash Lite as requested ("FLASHLIGHT")
            model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
            
            # Fetch valid specialties from the DB dynamically
            valid_specialties = [s[0] for s in Doctor._meta.get_field('specialty').choices]
            
            prompt = f"""
            You are an advanced Medical Diagnostic AI for the MediCureFlow platform. Your goal is to analyze patient symptoms and provide two distinct outputs: 
            1. A patient-friendly 'Health Insight' (empathetic, non-alarmist).
            2. A professional 'Clinical Summary' for the doctor (structured, data-driven). 
            **Note:** Always include a disclaimer at the start of patient insight that this is an AI-assisted analysis and not a final diagnosis.

            [PATIENT DATA]
            Symptoms: {symptoms}
            Duration: {duration}
            Severity: {severity}/10
            Medical History: {history}

            [TASK]
            1. Analyze the symptoms and provide a "Probable Condition" list.
            2. Create a "Patient Recommendation" (Lifestyle tips, urgency level).
            3. Create a "Doctor's Brief" including potential red flags and suggested initial tests.
            4. Select the VERY BEST matching specialty from this exact list of our database keys: {valid_specialties}. Return the exact string key exactly as it appears. If none match perfectly, use 'general_medicine' or 'general'.

            [OUTPUT FORMAT - JSON ONLY. NO MARKDOWN WRAPPERS OR BACKTICKS. JUST RAW JSON]
            {{
              "patient_view": {{
                "insight": "...",
                "next_steps": "...",
                "urgency_level": "..."
              }},
              "doctor_view": {{
                "summary": "...",
                "possible_diagnoses": ["...", "..."],
                "suggested_tests": ["...", "..."],
                "red_flags": "..."
              }},
              "recommended_specialty": "..."
            }}
            """

            response = model.generate_content(prompt)
            
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            ai_data = json.loads(cleaned_text)
            
            # Now access the database and select an available doctor
            raw_specialty = ai_data.get('recommended_specialty', '')
            specialty_key = str(raw_specialty).strip().lower()
            
            recommended_doctor = None
            if specialty_key:
                # Find an available doctor with this exact specialty (case insensitive)
                recommended_doctor = Doctor.objects.filter(specialty__iexact=specialty_key, is_available=True).order_by('?').first()
                
                # If exact matching fails, try a partial match (e.g., if AI returns 'cardiology' but key is 'cardiologist')
                if not recommended_doctor:
                    recommended_doctor = Doctor.objects.filter(specialty__icontains=specialty_key, is_available=True).order_by('?').first()

            # Fallback for General Medicine
            if not recommended_doctor:
                recommended_doctor = Doctor.objects.filter(specialty__icontains='general', is_available=True).order_by('?').first()
                
            # Final fallback
            if not recommended_doctor:
                recommended_doctor = Doctor.objects.filter(is_available=True).order_by('?').first()

            # Save doctor brief to session to attach to the Appointment
            if ai_data and 'doctor_view' in ai_data:
                request.session['ai_doctor_brief'] = ai_data['doctor_view']
            
            return render(request, 'users/smart_checkup/result.html', {
                'data': ai_data, 
                'doctor': recommended_doctor,
                'error': None
            })

            
        except Exception as e:
            return render(request, 'users/smart_checkup/result.html', {'data': None, 'error': str(e)})
            
    # GET request - show the form
    return render(request, 'users/smart_checkup/form.html')
