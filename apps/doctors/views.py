"""
Modern views for doctors app.

This module contains class-based views for doctor registration, authentication,
appointment management, and profile updates.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, FormView, DetailView, RedirectView
)
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Doctor, Appointment, DoctorAvailability, Review
from .forms import (
    DoctorRegistrationForm, DoctorProfileForm, AppointmentUpdateForm,
    DoctorAvailabilityForm, MedicationFormSet, TestReportFormSet
)
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


class DoctorSearchRedirectView(RedirectView):
    """
    Redirect doctor search to main search page.
    """
    permanent = False
    pattern_name = 'search_doctors'


class DoctorMixin(UserPassesTestMixin):
    """
    Mixin to ensure only doctors can access certain views.
    """
    def test_func(self):
        try:
            return hasattr(self.request.user, 'doctor_profile')
        except:
            return False
    
    def handle_no_permission(self):
        messages.error(self.request, 'You need to be a registered doctor to access this page.')
        return redirect('users:login')


class DoctorRegistrationView(CreateView):
    """
    Doctor registration view.
    """
    form_class = DoctorRegistrationForm
    template_name = 'doctors/register.html'
    success_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            'Doctor registration successful! You can now log in with your credentials.'
        )
        logger.info(f'New doctor registered: {form.cleaned_data["username"]}')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)




class DoctorLogoutView(LogoutView):
    """
    Doctor logout view.
    """
    next_page = reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        messages.success(request, 'You have been successfully logged out.')
        return super().dispatch(request, *args, **kwargs)


class DoctorDashboardView(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    Doctor dashboard view.
    """
    template_name = 'doctors/dashboard.html'
    login_url = reverse_lazy('users:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user.doctor_profile
        context['doctor'] = doctor
        
        # Import and use doctor analytics
        from apps.users.analytics import DoctorAnalytics
        analytics = DoctorAnalytics(doctor)
        
        # Get comprehensive dashboard statistics
        context.update({
            'dashboard_stats': analytics.get_dashboard_stats(),
            'appointment_trends': analytics.get_appointment_trends(),
            'rating_distribution': analytics.get_rating_distribution(),
            'peak_hours': analytics.get_peak_hours(),
            'patient_demographics': analytics.get_patient_demographics(),
            'revenue_trends': analytics.get_revenue_trends(),
            'revenue_performance': analytics.calculate_revenue_performance(),
            'total_earnings': analytics.calculate_total_earnings(),
        })
        
        # Add month names for revenue comparison
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        context['current_month_name'] = now.strftime('%B %Y')
        last_month = (now.replace(day=1) - timedelta(days=1))
        context['last_month_name'] = last_month.strftime('%B %Y')
        
        # Convert chart data to JSON for JavaScript
        import json
        context['appointment_trends_json'] = json.dumps(context['appointment_trends'])
        context['revenue_trends_json'] = json.dumps(context['revenue_trends'])
        context['rating_distribution_json'] = json.dumps(context['rating_distribution'])
        context['peak_hours_json'] = json.dumps(context['peak_hours'])
        
        # Get today's appointments
        from datetime import date
        today = date.today()
        context['todays_appointments'] = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today
        ).select_related('patient').order_by('appointment_time')
        
        # Get upcoming appointments
        context['upcoming_appointments'] = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gt=today
        ).select_related('patient').order_by('appointment_date', 'appointment_time')[:5]
        
        # Get recent reviews
        context['recent_reviews'] = Review.objects.filter(
            doctor=doctor,
            is_approved=True
        ).select_related('patient').order_by('-created_at')[:5]
        
        # Get doctor's availability schedule (CRITICAL: This was missing!)
        context['availability_slots'] = DoctorAvailability.objects.filter(
            doctor=doctor,
            is_active=True
        ).order_by('day_of_week', 'start_time')
        
        # Calculate availability statistics
        total_hours = 0
        active_days = set()
        for slot in context['availability_slots']:
            # Calculate hours for this slot
            start_minutes = slot.start_time.hour * 60 + slot.start_time.minute
            end_minutes = slot.end_time.hour * 60 + slot.end_time.minute
            slot_hours = (end_minutes - start_minutes) / 60
            total_hours += slot_hours
            active_days.add(slot.day_of_week)
        
        context['total_weekly_hours'] = int(total_hours)
        context['active_days'] = len(active_days)
        context['total_slots'] = context['availability_slots'].count()
        
        # Total patients
        from django.db.models import Count
        context['total_patients'] = Appointment.objects.filter(
            doctor=doctor
        ).values('patient').distinct().count()
        
        # Today's appointment count stat
        context['todays_appointments_count'] = Appointment.objects.filter(
            doctor=doctor, appointment_date=today
        ).count()
        
        # Monthly revenue
        from django.utils import timezone
        from django.db.models import Sum
        month_start = today.replace(day=1)
        context['monthly_revenue'] = Appointment.objects.filter(
            doctor=doctor, appointment_date__gte=month_start,
            status='completed'
        ).aggregate(total=Sum('fee_charged'))['total'] or 0
        
        # Merge upcoming with today for combined list
        context['upcoming_appointments'] = Appointment.objects.filter(
            doctor=doctor, appointment_date=today
        ).select_related('patient').order_by('appointment_time')[:5]
        
        # Get recent reviews
        context['recent_reviews'] = Review.objects.filter(
            doctor=doctor, is_approved=True
        ).select_related('patient').order_by('-created_at')[:3]
        
        # Convert chart data to JSON for JavaScript
        import json
        context['appointment_trends_json'] = json.dumps(context['appointment_trends'])
        context['rating_distribution_json'] = json.dumps(context['rating_distribution'])
        context['peak_hours_json'] = json.dumps(context['peak_hours'])
        
        return context


class DoctorProfileView(LoginRequiredMixin, DoctorMixin, UpdateView):
    """
    Doctor profile update view with comprehensive statistics.
    """
    model = Doctor
    form_class = DoctorProfileForm
    template_name = 'doctors/profile.html'
    success_url = reverse_lazy('doctors:profile')
    login_url = reverse_lazy('users:login')
    
    def get_object(self, queryset=None):
        return self.request.user.doctor_profile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.get_object()
        
        # Add comprehensive statistics (same as admin view)
        context['total_appointments'] = doctor.appointments.count()
        context['completed_appointments'] = doctor.appointments.filter(status='completed').count()
        context['upcoming_appointments'] = doctor.appointments.filter(
            status__in=['scheduled', 'confirmed'],
            appointment_date__gte=timezone.now().date()
        ).count()
        
        # Calculate total earnings from completed appointments
        completed_appointments = doctor.appointments.filter(status='completed')
        total_earnings = sum(apt.fee_charged or doctor.consultation_fee for apt in completed_appointments)
        context['total_earnings'] = total_earnings
        
        # Recent reviews and average rating
        context['recent_reviews'] = doctor.reviews.order_by('-created_at')[:5]
        from django.db.models import Avg
        context['avg_rating'] = doctor.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        context['total_reviews'] = doctor.reviews.count()
        
        # Recent appointments
        context['recent_appointments'] = doctor.appointments.select_related('patient').order_by('-created_at')[:10]
        
        # Patient count (unique patients)
        context['total_patients'] = doctor.appointments.values('patient').distinct().count()
        
        # This month's statistics
        from datetime import date
        current_month = date.today().replace(day=1)
        context['this_month_appointments'] = doctor.appointments.filter(
            appointment_date__gte=current_month
        ).count()
        context['this_month_earnings'] = sum(
            apt.fee_charged or doctor.consultation_fee 
            for apt in doctor.appointments.filter(
                status='completed',
                appointment_date__gte=current_month
            )
        )
        
        # Success rate
        if context['total_appointments'] > 0:
            context['success_rate'] = (context['completed_appointments'] / context['total_appointments']) * 100
        else:
            context['success_rate'] = 0
            
        # Currency info for templates
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
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class DoctorAnalyticsView(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    Detailed analytics for the logged-in doctor.
    """
    template_name = 'doctors/analytics.html'
    login_url = reverse_lazy('users:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user.doctor_profile
        today = timezone.now().date()
        six_months_ago = today - timezone.timedelta(days=180)

        # Basic Stats
        context['total_appointments'] = Appointment.objects.filter(doctor=doctor).count()
        context['completed_appointments'] = Appointment.objects.filter(doctor=doctor, status='completed').count()
        
        # Monthly Revenue Trend (Last 6 Months)
        from django.db.models.functions import TruncMonth
        from django.db.models import Sum, Count
        
        revenue_trends = Appointment.objects.filter(
            doctor=doctor, 
            status='completed',
            appointment_date__gte=six_months_ago
        ).annotate(month=TruncMonth('appointment_date')).values('month').annotate(
            revenue=Sum('fee_charged'),
            count=Count('id')
        ).order_by('month')
        
        context['revenue_labels'] = [entry['month'].strftime('%b %Y') for entry in revenue_trends]
        context['revenue_values'] = [float(entry['revenue'] or 0) for entry in revenue_trends]
        context['revenue_counts'] = [entry['count'] for entry in revenue_trends]

        # Specialty Comparison / Performance
        context['specialty_avg_fee'] = Appointment.objects.filter(
            doctor__specialty=doctor.specialty,
            status='completed'
        ).aggregate(avg_fee=Sum('fee_charged'))['avg_fee'] or 0

        # Patient Demographics
        gender_map = {'M': 'Male', 'F': 'Female', 'O': 'Other', 'P': 'Prefer not to say'}
        gender_data = Appointment.objects.filter(doctor=doctor).values('patient__profile__gender').annotate(count=Count('id'))
        context['gender_labels'] = [gender_map.get(entry['patient__profile__gender'], 'Unknown') for entry in gender_data]
        context['gender_counts'] = [entry['count'] for entry in gender_data]

        import json
        context['revenue_labels_json'] = json.dumps(context['revenue_labels'])
        context['revenue_values_json'] = json.dumps(context['revenue_values'])
        context['gender_labels_json'] = json.dumps(context['gender_labels'])
        context['gender_counts_json'] = json.dumps(context['gender_counts'])

        return context


class DoctorAppointmentsView(LoginRequiredMixin, DoctorMixin, ListView):
    """
    Doctor's appointments list view with improved reliability.
    """
    model = Appointment
    template_name = 'doctors/appointments.html'
    context_object_name = 'appointments'
    login_url = reverse_lazy('users:login')
    paginate_by = 15
    
    def get_queryset(self):
        try:
            doctor = self.request.user.doctor_profile
            status = self.request.GET.get('status')
            date_filter = self.request.GET.get('date')
            
            # Use select_related to optimize queries and avoid N+1 problems
            queryset = Appointment.objects.select_related('patient', 'patient__profile', 'doctor').filter(doctor=doctor)
            
            # Filter by status
            if status and status != 'all':
                queryset = queryset.filter(status=status)
            
            # Filter by date
            if date_filter:
                try:
                    # Django automatically handles 'YYYY-MM-DD' strings for DateField
                    queryset = queryset.filter(appointment_date=date_filter)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid date filter provided: {date_filter}")
            
            return queryset.order_by('-appointment_date', '-appointment_time')
            
        except Exception as e:
            logger.error(f'Error in get_queryset for appointments: {str(e)}')
            messages.error(self.request, 'Unable to load appointments. Please try again.')
            return Appointment.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            context['status_filter'] = self.request.GET.get('status', 'all')
            context['status_choices'] = Appointment.STATUS_CHOICES
            
            doctor = self.request.user.doctor_profile
            
            # Calculate accurate appointment statistics with error handling
            from datetime import date
            today = date.today()
            
            # Initialize all context variables with defaults
            context.update({
                'todays_total': 0,
                'todays_confirmed': 0,
                'todays_completed': 0,
                'todays_earnings': 0,
                'total_appointments': 0,
                'completed_appointments': 0,
                'upcoming_appointments': 0,
                'total_earnings': 0
            })
            
            try:
                # Today's appointments
                todays_appointments = doctor.appointments.filter(appointment_date=today)
                context['todays_total'] = todays_appointments.count()
                context['todays_confirmed'] = todays_appointments.filter(
                    status__in=['confirmed', 'scheduled']
                ).count()
                context['todays_completed'] = todays_appointments.filter(status='completed').count()
                
                # Today's earnings (only from completed appointments today)
                todays_completed_appointments = todays_appointments.filter(status='completed')
                context['todays_earnings'] = sum(
                    (apt.fee_charged or doctor.consultation_fee or 0) 
                    for apt in todays_completed_appointments
                )
                
                # Overall statistics (for consistency with profile)
                context['total_appointments'] = doctor.appointments.count()
                context['completed_appointments'] = doctor.appointments.filter(status='completed').count()
                context['upcoming_appointments'] = doctor.appointments.filter(
                    status__in=['scheduled', 'confirmed'],
                    appointment_date__gte=today
                ).count()
                
                # Total earnings from all completed appointments
                completed_appointments = doctor.appointments.filter(status='completed')
                context['total_earnings'] = sum(
                    (apt.fee_charged or doctor.consultation_fee or 0) 
                    for apt in completed_appointments
                )
                
            except Exception as e:
                logger.error(f'Error calculating appointment statistics: {str(e)}')
                # Context defaults are already set above
            
            # Currency info for templates
            from django.conf import settings
            currency = getattr(settings, 'DEFAULT_CURRENCY', 'INR')
            currency_symbols = getattr(settings, 'CURRENCY_SYMBOLS', {
                'USD': '$',
                'INR': '₹',
                'EUR': '€',
                'GBP': '£'
            })
            context['current_currency'] = currency
            context['currency_symbol'] = currency_symbols.get(currency, '₹')
            
            # Pass all other doctors for the referral dropdown
            context['all_doctors'] = Doctor.objects.filter(
                is_available=True
            ).exclude(id=doctor.id).order_by('first_name', 'last_name')
            
        except Exception as e:
            logger.error(f'Error in get_context_data for appointments: {str(e)}')
            messages.error(self.request, 'Error loading appointment data.')
            # Provide minimal context to prevent template errors
            context.update({
                'status_filter': 'all',
                'status_choices': [],
                'todays_total': 0,
                'todays_confirmed': 0,
                'todays_completed': 0,
                'todays_earnings': 0,
                'total_appointments': 0,
                'completed_appointments': 0,
                'upcoming_appointments': 0,
                'total_earnings': 0,
                'current_currency': 'INR',
                'currency_symbol': '₹'
            })
        
        return context


class AppointmentUpdateView(LoginRequiredMixin, DoctorMixin, UpdateView):
    """
    Update appointment status and notes.
    """
    model = Appointment
    form_class = AppointmentUpdateForm
    template_name = 'doctors/appointment_update.html'
    success_url = reverse_lazy('doctors:appointments')
    login_url = reverse_lazy('users:login')
    
    def get_queryset(self):
        # Only allow doctor to update their own appointments
        return Appointment.objects.filter(doctor=self.request.user.doctor_profile)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['medication_formset'] = MedicationFormSet(self.request.POST, instance=self.object)
            context['report_formset'] = TestReportFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context['medication_formset'] = MedicationFormSet(instance=self.object)
            context['report_formset'] = TestReportFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        medication_formset = context['medication_formset']
        report_formset = context['report_formset']
        
        if medication_formset.is_valid() and report_formset.is_valid():
            self.object = form.save()
            medication_formset.instance = self.object
            medication_formset.save()
            report_formset.instance = self.object
            report_formset.save()
            
            messages.success(self.request, 'Appointment results, medications, and reports saved successfully!')
            logger.info(
                f'Appointment {self.object.id} updated by doctor {self.request.user.username}'
            )
            return redirect(self.get_success_url())
        else:
            return self.form_invalid(form)


class AppointmentCreateView(LoginRequiredMixin, DoctorMixin, CreateView):
    """
    Create new appointment by doctor.
    """
    model = Appointment
    template_name = 'doctors/appointment_create.html'
    success_url = reverse_lazy('doctors:appointments')
    login_url = reverse_lazy('users:login')
    fields = ['patient', 'appointment_date', 'appointment_time', 'duration_minutes', 'patient_notes', 'fee_charged']
    
    def form_valid(self, form):
        form.instance.doctor = self.request.user.doctor_profile
        form.instance.status = 'scheduled'
        
        # Set default fee if not provided
        if not form.instance.fee_charged:
            form.instance.fee_charged = self.request.user.doctor_profile.consultation_fee
            
        messages.success(self.request, 'Appointment scheduled successfully!')
        logger.info(
            f'New appointment created by doctor {self.request.user.username} for patient {form.instance.patient}'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doctor'] = self.request.user.doctor_profile
        
        # Get available patients (those who have user profiles)
        from apps.users.models import UserProfile
        available_patients = User.objects.filter(
            profile__isnull=False,
        ).exclude(
            doctor_profile__isnull=False  # Exclude doctors from patient list
        ).order_by('first_name', 'last_name')
        
        context['available_patients'] = available_patients
        return context


class DoctorAvailabilityView(LoginRequiredMixin, DoctorMixin, ListView):
    """
    Comprehensive doctor availability management.
    """
    model = DoctorAvailability
    template_name = 'doctors/availability.html'
    context_object_name = 'availability_slots'
    login_url = reverse_lazy('users:login')
    
    def get_queryset(self):
        return DoctorAvailability.objects.filter(
            doctor=self.request.user.doctor_profile
        ).order_by('day_of_week', 'start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user.doctor_profile
        availability_slots = self.get_queryset()
        
        context['doctor'] = doctor
        context['form'] = DoctorAvailabilityForm()
        
        # Calculate statistics
        total_hours = 0
        active_days = set()
        
        for slot in availability_slots:
            if slot.is_active:
                # Calculate hours for this slot
                start_minutes = slot.start_time.hour * 60 + slot.start_time.minute
                end_minutes = slot.end_time.hour * 60 + slot.end_time.minute
                slot_hours = (end_minutes - start_minutes) / 60
                total_hours += slot_hours
                active_days.add(slot.day_of_week)
        
        context['total_hours'] = total_hours
        context['active_days'] = len(active_days)
        
        return context


class AddAvailabilityView(LoginRequiredMixin, DoctorMixin, CreateView):
    """
    Add new availability slot.
    """
    model = DoctorAvailability
    form_class = DoctorAvailabilityForm
    template_name = 'doctors/add_availability.html'
    success_url = reverse_lazy('doctors:availability')
    login_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        form.instance.doctor = self.request.user.doctor_profile
        messages.success(self.request, 'Availability slot added successfully!')
        return super().form_valid(form)


class AddAvailabilityAjaxView(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    AJAX endpoint for adding availability slots.
    """
    http_method_names = ['post']
    
    def post(self, request):
        try:
            doctor = request.user.doctor_profile
            
            # Get form data
            day_of_week = request.POST.get('day_of_week')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            is_active = request.POST.get('is_active') == 'on'
            
            # Validate required fields
            if not all([day_of_week, start_time, end_time]):
                return JsonResponse({
                    'success': False,
                    'message': 'Please fill in all required fields'
                })
            
            # Check for overlapping slots
            from datetime import datetime
            start_dt = datetime.strptime(start_time, '%H:%M').time()
            end_dt = datetime.strptime(end_time, '%H:%M').time()
            
            if start_dt >= end_dt:
                return JsonResponse({
                    'success': False,
                    'message': 'End time must be after start time'
                })
            
            # Check for existing overlapping slots
            existing_slots = DoctorAvailability.objects.filter(
                doctor=doctor,
                day_of_week=day_of_week,
                is_active=True
            )
            
            for slot in existing_slots:
                if not (end_dt <= slot.start_time or start_dt >= slot.end_time):
                    return JsonResponse({
                        'success': False,
                        'message': f'Time slot overlaps with existing slot ({slot.start_time.strftime("%H:%M")} - {slot.end_time.strftime("%H:%M")})'
                    })
            
            # Create the availability slot
            availability = DoctorAvailability.objects.create(
                doctor=doctor,
                day_of_week=int(day_of_week),
                start_time=start_dt,
                end_time=end_dt,
                is_active=is_active
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Availability slot added successfully!',
                'slot_id': availability.id
            })
            
        except Exception as e:
            logger.error(f'Error adding availability slot: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while adding the slot'
            })


class DeleteAvailabilityView(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    Delete availability slot.
    """
    http_method_names = ['delete']
    
    def delete(self, request, slot_id):
        try:
            doctor = request.user.doctor_profile
            
            # Get the slot and ensure it belongs to the doctor
            slot = get_object_or_404(DoctorAvailability, id=slot_id, doctor=doctor)
            
            # Delete the slot
            slot.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Availability slot deleted successfully'
            })
            
        except DoctorAvailability.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Availability slot not found'
            })
        except Exception as e:
            logger.error(f'Error deleting availability slot: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while deleting the slot'
            })


class UpdateAvailabilityView(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    Update availability slot details (inline editing).
    """
    http_method_names = ['post']
    
    def post(self, request, slot_id):
        try:
            import json
            from datetime import datetime
            
            doctor = request.user.doctor_profile
            
            # Get the slot and ensure it belongs to the doctor
            slot = get_object_or_404(DoctorAvailability, id=slot_id, doctor=doctor)
            
            # Parse JSON data
            data = json.loads(request.body)
            
            # Get updated values (use existing values if not provided)
            start_time_str = data.get('start_time')
            end_time_str = data.get('end_time')
            is_active = data.get('is_active')
            
            # Update fields if provided
            if start_time_str is not None:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                slot.start_time = start_time
            
            if end_time_str is not None:
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                slot.end_time = end_time
            
            if is_active is not None:
                slot.is_active = is_active
            
            # Validate times if both are being updated
            if slot.start_time >= slot.end_time:
                return JsonResponse({
                    'success': False,
                    'message': 'End time must be after start time'
                })
            
            # Check for overlapping slots (exclude current slot)
            if start_time_str or end_time_str:
                existing_slots = DoctorAvailability.objects.filter(
                    doctor=doctor,
                    day_of_week=slot.day_of_week,
                    is_active=True
                ).exclude(id=slot.id)
                
                for existing_slot in existing_slots:
                    if not (slot.end_time <= existing_slot.start_time or slot.start_time >= existing_slot.end_time):
                        return JsonResponse({
                            'success': False,
                            'message': f'Time slot overlaps with existing slot ({existing_slot.start_time.strftime("%H:%M")} - {existing_slot.end_time.strftime("%H:%M")})'
                        })
            
            # Save the updated slot
            slot.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Availability slot updated successfully'
            })
            
        except DoctorAvailability.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Availability slot not found'
            })
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': 'Invalid time format'
            })
        except Exception as e:
            logger.error(f'Error updating availability slot: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while updating the slot'
            })


class ToggleAvailabilityView(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    Toggle doctor's overall availability status.
    """
    http_method_names = ['post']
    
    def post(self, request):
        try:
            import json
            data = json.loads(request.body)
            available = data.get('available')
            on_duty = data.get('on_duty')
            
            doctor = request.user.doctor_profile
            
            if available is not None:
                doctor.is_available = available
                doctor.save(update_fields=['is_available'])
                status_text = 'available' if available else 'unavailable'
                message = f'You are now marked as {status_text}'
                
            elif on_duty is not None:
                doctor.is_on_duty = on_duty
                doctor.save(update_fields=['is_on_duty'])
                status_text = 'on duty' if on_duty else 'off duty'
                message = f'Work Mode is now {status_text}'
            
            return JsonResponse({
                'success': True,
                'message': message,
                'available': doctor.is_available,
                'on_duty': doctor.is_on_duty
            })
            
        except Exception as e:
            logger.error(f'Error toggling availability: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while updating availability'
            })


class DoctorDetailView(DetailView):
    """
    Public doctor detail view.
    """
    model = Doctor
    template_name = 'doctors/detail.html'
    context_object_name = 'doctor'
    
    def get_queryset(self):
        return Doctor.objects.filter(is_available=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.object
        
        # Get doctor's availability
        context['availability'] = DoctorAvailability.objects.filter(
            doctor=doctor, is_active=True
        ).order_by('day_of_week', 'start_time')
        
        # Get recent reviews
        context['reviews'] = Review.objects.filter(
            doctor=doctor, is_approved=True
        ).order_by('-created_at')[:10]
        
        # Calculate average rating
        reviews = doctor.reviews.filter(is_approved=True)
        if reviews.exists():
            from django.db.models import Avg
            context['average_rating'] = reviews.aggregate(Avg('rating'))['rating__avg']
            context['total_reviews'] = reviews.count()
        else:
            context['average_rating'] = 0
            context['total_reviews'] = 0
        
        return context


# Legacy function-based views for compatibility
def doctor_registration_view(request):
    """Redirect to class-based view."""
    return redirect('doctors:register')

def doctor_login_view(request):
    """Redirect to class-based view."""
    return redirect('users:login')

def doctor_appointments_view(request):
    """Redirect to class-based view."""
    return redirect('doctors:appointments')

def doctor_profile_view(request):
    """Redirect to class-based view."""
    return redirect('doctors:profile')

def doctor_change_password_view(request):
    """Redirect to password change view."""
    return redirect('doctors:password_change')

def doctor_logout_view(request):
    """Redirect to class-based view."""
    return redirect('doctors:logout')


# API Views for AJAX requests
class AppointmentStatusUpdateAPI(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    API view to update appointment status.
    """
    http_method_names = ['post']
    
    def post(self, request, appointment_id):
        try:
            # Validate appointment ID
            if not appointment_id or not str(appointment_id).isdigit():
                return JsonResponse({'success': False, 'message': 'Invalid appointment ID'})
                
            data = json.loads(request.body)
            new_status = data.get('status')
            
            # Validate status
            valid_statuses = ['scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': 'Invalid status'})
            
            # Get appointment and ensure it belongs to the doctor
            appointment = get_object_or_404(
                Appointment, 
                id=appointment_id, 
                doctor=request.user.doctor_profile
            )
            
            # Validate status transition
            if appointment.status == 'completed' and new_status != 'completed':
                return JsonResponse({'success': False, 'message': 'Cannot change status of completed appointment'})
            
            # Update status
            old_status = appointment.status
            appointment.status = new_status
            appointment.save()
            
            logger.info(f'Appointment {appointment_id} status updated from {old_status} to {new_status} by doctor {request.user.username}')
            
            return JsonResponse({
                'success': True, 
                'message': f'Appointment status updated to {appointment.get_status_display()}',
                'new_status': appointment.get_status_display()
            })
            
        except json.JSONDecodeError:
            logger.error(f'Invalid JSON data in status update request')
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Appointment.DoesNotExist:
            logger.error(f'Appointment {appointment_id} not found or not owned by doctor {request.user.username}')
            return JsonResponse({'success': False, 'message': 'Appointment not found'})
        except Exception as e:
            logger.error(f'Error updating appointment status: {str(e)}')
            return JsonResponse({'success': False, 'message': 'Server error occurred'})


class AppointmentCompleteAPI(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    API view to complete an appointment with notes.
    """
    http_method_names = ['post']
    
    def post(self, request, appointment_id):
        try:
            # Validate appointment ID
            if not appointment_id or not str(appointment_id).isdigit():
                return JsonResponse({'success': False, 'message': 'Invalid appointment ID'})
                
            data = json.loads(request.body)
            
            # Get appointment and ensure it belongs to the doctor
            appointment = get_object_or_404(
                Appointment, 
                id=appointment_id, 
                doctor=request.user.doctor_profile
            )
            
            # Validate appointment can be completed
            if appointment.status == 'cancelled':
                return JsonResponse({'success': False, 'message': 'Cannot complete a cancelled appointment'})
            if appointment.status == 'completed':
                return JsonResponse({'success': False, 'message': 'Appointment is already completed'})
            
            # Update appointment details
            old_status = appointment.status
            appointment.status = 'completed'
            appointment.doctor_notes = data.get('doctor_notes', appointment.doctor_notes or '')
            
            # Validate and set duration
            duration = data.get('duration_minutes')
            if duration:
                try:
                    duration = int(duration)
                    if 5 <= duration <= 180:  # 5 minutes to 3 hours
                        appointment.duration_minutes = duration
                except (ValueError, TypeError):
                    pass  # Keep existing duration if invalid
            
            appointment.save()
            
            logger.info(f'Appointment {appointment_id} completed (was {old_status}) by doctor {request.user.username}')
            
            return JsonResponse({
                'success': True, 
                'message': 'Appointment completed successfully'
            })
            
        except json.JSONDecodeError:
            logger.error(f'Invalid JSON data in complete appointment request')
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Appointment.DoesNotExist:
            logger.error(f'Appointment {appointment_id} not found or not owned by doctor {request.user.username}')
            return JsonResponse({'success': False, 'message': 'Appointment not found'})
        except Exception as e:
            logger.error(f'Error completing appointment {appointment_id}: {str(e)}')
            return JsonResponse({'success': False, 'message': 'Server error occurred'})


class AppointmentNotesUpdateAPI(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    API view to update appointment notes.
    """
    http_method_names = ['post']
    
    def post(self, request, appointment_id):
        try:
            # Validate appointment ID
            if not appointment_id or not str(appointment_id).isdigit():
                return JsonResponse({'success': False, 'message': 'Invalid appointment ID'})
                
            data = json.loads(request.body)
            
            # Get appointment and ensure it belongs to the doctor
            appointment = get_object_or_404(
                Appointment, 
                id=appointment_id, 
                doctor=request.user.doctor_profile
            )
            
            # Update notes
            new_notes = data.get('doctor_notes', '')
            if isinstance(new_notes, str):
                appointment.doctor_notes = new_notes
                appointment.save()
                
                logger.info(f'Notes updated for appointment {appointment_id} by doctor {request.user.username}')
                
                return JsonResponse({
                    'success': True, 
                    'message': 'Notes updated successfully'
                })
            else:
                return JsonResponse({'success': False, 'message': 'Invalid notes format'})
            
        except json.JSONDecodeError:
            logger.error(f'Invalid JSON data in update notes request')
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Appointment.DoesNotExist:
            logger.error(f'Appointment {appointment_id} not found or not owned by doctor {request.user.username}')
            return JsonResponse({'success': False, 'message': 'Appointment not found'})
        except Exception as e:
            logger.error(f'Error updating notes for appointment {appointment_id}: {str(e)}')
            return JsonResponse({'success': False, 'message': 'Server error occurred'})


class DoctorAvailableSlotsView(TemplateView):
    """
    View to fetch available time slots for a doctor on a specific date.
    """
    def get(self, request, *args, **kwargs):
        doctor_id = request.GET.get('doctor_id')
        date_str = request.GET.get('date')
        
        if not doctor_id or not date_str:
            return JsonResponse({'success': False, 'error': 'Missing doctor_id or date'})
        
        try:
            doctor = Doctor.objects.get(id=doctor_id)
            # Check if doctor is accepting appointments at all globally
            if not doctor.is_available:
                return JsonResponse({
                    'success': True, 
                    'slots': [],
                    'message': 'Doctor is currently unavailable for new appointments.'
                })

            from datetime import datetime, time
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            day_of_week = date_obj.weekday()
            
            # Get availability for this day
            availabilities = DoctorAvailability.objects.filter(
                doctor=doctor, 
                day_of_week=day_of_week,
                is_active=True
            ).order_by('start_time')
            
            # Use defined availabilities or default to 9AM-6PM
            active_ranges = []
            if availabilities.exists():
                for a in availabilities:
                    active_ranges.append((a.start_time, a.end_time))
            else:
                # Check if doctor has ANY availability defined globally
                has_any_availability = DoctorAvailability.objects.filter(
                    doctor=doctor, 
                    is_active=True
                ).exists()
                
                if not has_any_availability:
                    return JsonResponse({
                        'success': True, 
                        'slots': [],
                        'message': 'Doctor has not yet set up their availability schedule.'
                    })
                else:
                    return JsonResponse({
                        'success': True, 
                        'slots': [],
                        'message': 'No available slots for this date.'
                    })
            
            # Get already booked appointments for this date
            booked_appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date_obj,
                status__in=['scheduled', 'confirmed', 'in_progress']
            ).values_list('appointment_time', flat=True)
            
            slots = []
            for start, end in active_ranges:
                # Generate slots every 30 minutes
                current = datetime.combine(date_obj, start)
                limit = datetime.combine(date_obj, end)
                
                while current < limit:
                    slot_time = current.time()
                    
                    # Check if slot is booked
                    is_booked = any(b.hour == slot_time.hour and b.minute == slot_time.minute for b in booked_appointments)
                    
                    # Check if slot is during lunch break
                    is_lunch = False
                    if doctor.lunch_break_start and doctor.lunch_break_end:
                        if doctor.lunch_break_start <= slot_time < doctor.lunch_break_end:
                            is_lunch = True
                    
                    # Check if slot is in the past (if date is today)
                    is_past = False
                    local_now = timezone.localtime()
                    if date_obj == local_now.date():
                        if slot_time <= local_now.time():
                            is_past = True
                    
                    if not is_booked and not is_lunch and not is_past:
                        slots.append({
                            'time': slot_time.strftime('%H:%M'),
                            'display_time': slot_time.strftime('%I:%M %p')
                        })
                    
                    current += timezone.timedelta(minutes=30)
            
            return JsonResponse({'success': True, 'slots': slots})
            
        except Doctor.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Doctor not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


@method_decorator(csrf_exempt, name='dispatch')
class WhisperTranscribeAPI(View):
    """
    API view to transcribe audio using OpenAI Whisper model.
    """
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
            
        if 'audio' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No audio file provided'})
            
        audio_file = request.FILES['audio']
        
        # Save audio file to temp directory
        import tempfile
        import os
        import whisper
        from django.conf import settings
        
        # Load local whisper model (singleton-ish)
        if not hasattr(WhisperTranscribeAPI, '_model'):
            # Use 'base' for speed/accuracy balance. Alternatives: 'tiny', 'small', 'medium', 'large'
            WhisperTranscribeAPI._model = whisper.load_model("base")
            
        temp_dir = tempfile.gettempdir()
        temp_name = os.path.join(temp_dir, f"audio_{request.user.id}_{int(timezone.now().timestamp())}.webm")
        
        try:
            with open(temp_name, 'wb+') as destination:
                for chunk in audio_file.chunks():
                    destination.write(chunk)
            
            # Use local model for transcription
            result = WhisperTranscribeAPI._model.transcribe(temp_name)
            
            return JsonResponse({
                'success': True, 
                'text': result.get("text", "").strip()
            })
            
        except Exception as e:
            logger.error(f"Whisper transcription error: {str(e)}")
            return JsonResponse({'success': False, 'message': str(e)})
        finally:
            if os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except:
                    pass


class CheckAvailabilityAPI(LoginRequiredMixin, View):
    """
    API view to check if a specific date and time is available for a doctor.
    Used for follow-up scheduling in consultation modal.
    """
    def get(self, request, *args, **kwargs):
        doctor_id = request.GET.get('doctor_id')
        
        # Security check: If not specified, default to current doctor. 
        # If specified, ensure requester has permission or it's a valid public check.
        if not doctor_id:
            try:
                doctor_id = request.user.doctor_profile.id
            except AttributeError:
                return JsonResponse({'success': False, 'message': 'Doctor profile not found'}, status=403)

        date_str = request.GET.get('date')
        time_str = request.GET.get('time')
        
        if not all([doctor_id, date_str, time_str]):
            return JsonResponse({'success': False, 'message': 'Missing required parameters: doctor_id, date, and time'})
            
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            doctor = get_object_or_404(Doctor, id=doctor_id)
            
            # Check for existing appointments at this exact slot
            conflict = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date_obj,
                appointment_time=time_obj,
                status__in=['scheduled', 'confirmed', 'in_progress']
            ).exists()
            
            if conflict:
                return JsonResponse({
                    'success': True, 
                    'available': False, 
                    'message': 'This slot is already booked by another patient.'
                })
            
            # Check availability schedule for this day
            day_of_week = date_obj.weekday()
            avail_slots = DoctorAvailability.objects.filter(
                doctor=doctor,
                day_of_week=day_of_week,
                is_active=True,
                start_time__lte=time_obj,
                end_time__gt=time_obj
            )
            
            is_available = avail_slots.exists()
            
            # Custom availability is strictly enforced for all doctors
            if not is_available:
                from datetime import time as dt_time
            
            # Check for lunch break exclusion
            if is_available and doctor.lunch_break_start and doctor.lunch_break_end:
                if doctor.lunch_break_start <= time_obj < doctor.lunch_break_end:
                    is_available = False
                    return JsonResponse({
                        'success': True, 
                        'available': False, 
                        'message': 'Doctor is on lunch break at this time.'
                    })
            
            return JsonResponse({
                'success': True, 
                'available': is_available,
                'message': 'Slot is available for booking.' if is_available else 'Doctor is not scheduled to work at this time.'
            })
            
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date or time format. Expected YYYY-MM-DD and HH:MM.'})
        except Exception as e:
            logger.error(f"Availability check error: {str(e)}")
            return JsonResponse({'success': False, 'message': 'An internal error occurred during availability check.'})


class AppointmentConsultationAPI(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    API view to save consultation remarks, prescriptions, and diagnostic test reports.
    Supports both JSON and multipart/form-data for file uploads.
    """
    http_method_names = ['post']
    
    def post(self, request, appointment_id):
        try:
            # Check content type and parse data accordingly
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                # Handle multipart/form-data for file uploads
                data = request.POST.dict()
                # Parse the medicines JSON if sent as a field in FormData
                if 'medicines_json' in data:
                    try:
                        data['medicines'] = json.loads(data['medicines_json'])
                    except json.JSONDecodeError:
                        data['medicines'] = []

            appointment = get_object_or_404(
                Appointment, 
                id=appointment_id, 
                doctor=request.user.doctor_profile
            )
            
            # Save core consultation data
            appointment.consultation_remarks = data.get('remarks', '')
            next_date = data.get('next_date')
            next_time = data.get('next_time')
            recommended_doc_id = data.get('recommended_doctor_id')
            
            if next_date:
                appointment.next_appointment_date = next_date
            if next_time:
                appointment.next_appointment_time = next_time
            if recommended_doc_id:
                appointment.recommended_doctor_id = recommended_doc_id
                
            appointment.status = 'completed'
            appointment.save()
            
            # 1. Update/Create Medications
            medicines = data.get('medicines', [])
            if medicines:
                from .models import Medication
                appointment.medications.all().delete()
                
                med_objects = []
                for med in medicines:
                    if med.get('name'):
                        med_objects.append(
                            Medication(
                                appointment=appointment,
                                name=med.get('name')[:200],
                                amount=med.get('amount', '')[:100],
                                dosage=med.get('dosage', '')[:100],
                                eating_quantity=med.get('eating_quantity', '')[:100],
                                notes=med.get('notes', '')[:255]
                            )
                        )
                if med_objects:
                    Medication.objects.bulk_create(med_objects)
            
            # 2. Handle Test Report Uploads
            # Expecting fields like 'test_name_0', 'test_file_0', 'test_name_1', 'test_file_1', etc.
            from .models import TestReport
            
            test_indices = set()
            for key in request.POST.keys():
                if key.startswith('test_name_'):
                    index = key.replace('test_name_', '')
                    test_indices.add(index)
            
            for index in test_indices:
                test_name = request.POST.get(f'test_name_{index}')
                test_file = request.FILES.get(f'test_file_{index}')
                
                if test_name and test_file:
                    TestReport.objects.create(
                        appointment=appointment,
                        test_name=test_name[:200],
                        report_file=test_file
                    )
            
            # Create notification for patient
            from apps.notifications.services import NotificationService
            
            service = NotificationService()
            service.create_notification(
                recipient=appointment.patient,
                notification_type='Appointment Completed',
                title="Consultation Completed",
                message=f"Dr. {appointment.doctor.last_name} has completed your consultation. Please check your dashboard for remarks and follow-up details.",
                content_object=appointment
            )
            
            return JsonResponse({'success': True, 'message': 'Consultation and reports saved successfully'})
            
        except Exception as e:
            logger.error(f'Error in AppointmentConsultationAPI: {str(e)}')
            return JsonResponse({'success': False, 'message': str(e)})


class PatientHistoryAPI(LoginRequiredMixin, DoctorMixin, TemplateView):
    """
    API view to fetch past consultation history for a patient, including test reports.
    """
    def get(self, request, patient_id):
        try:
            # Get only completed appointments for this patient
            history = Appointment.objects.filter(
                patient_id=patient_id,
                status='completed'
            ).order_by('appointment_date', 'appointment_time').prefetch_related('test_reports')
            
            data = []
            for appt in history:
                reports = []
                for report in appt.test_reports.all():
                    reports.append({
                        'name': report.test_name,
                        'url': report.report_file.url if report.report_file else None
                    })
                
                data.append({
                    'id': appt.id,
                    'date': appt.appointment_date.strftime('%d %b, %Y'),
                    'doctor': appt.doctor.display_name,
                    'remarks': appt.consultation_remarks or "No remarks provided.",
                    'notes': appt.patient_notes or "N/A",
                    'reports': reports
                })
            
            return JsonResponse({'success': True, 'history': data})
        except Exception as e:
            logger.error(f'Error in PatientHistoryAPI: {str(e)}')
            return JsonResponse({'success': False, 'message': str(e)})

def serve_doctor_profile_image(request, doctor_id):
    """Serve the profile picture from SQLite binary storage."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    if doctor.photo_blob and doctor.photo_mime:
        return HttpResponse(doctor.photo_blob, content_type=doctor.photo_mime)
    raise Http404("Doctor photo not found")
