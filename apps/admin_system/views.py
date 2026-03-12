"""
MediCureFlow Admin System Views
Powerful admin interface with complete system control
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import csv
from datetime import datetime, timedelta
from io import StringIO
from django.conf import settings

from .models import AdminActivity, SystemAlert, AdminConfiguration
from .signals import log_admin_activity
from apps.users.models import UserProfile
from apps.doctors.models import Doctor, Appointment, Review
# from apps.health_ai.models import HealthCheckup


def is_admin(user):
    """Check if user is admin"""
    return user.is_authenticated and user.is_staff


class AdminOnlyMixin(UserPassesTestMixin):
    """Mixin to ensure only admin users can access views"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Main admin dashboard with comprehensive analytics"""
    # Get current date for analytics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Basic counts
    total_users = User.objects.filter(is_staff=False).count()
    total_doctors = Doctor.objects.count()
    total_appointments = Appointment.objects.count()
    total_reviews = Review.objects.count()
    # total_checkups = HealthCheckup.objects.count()
    total_checkups = 0
    
    # Recent activity counts
    new_users_week = User.objects.filter(date_joined__gte=week_ago, is_staff=False).count()
    new_doctors_week = Doctor.objects.filter(created_at__gte=week_ago).count()
    new_appointments_week = Appointment.objects.filter(created_at__gte=week_ago).count()
    
    # System alerts
    critical_alerts = SystemAlert.objects.filter(severity='critical', is_resolved=False).count()
    high_alerts = SystemAlert.objects.filter(severity='high', is_resolved=False).count()
    unread_alerts = SystemAlert.objects.filter(is_read=False).count()
    
    # Recent activities
    recent_activities = AdminActivity.objects.select_related('admin').order_by('-timestamp')[:10]
    
    # Appointment status breakdown
    appointment_stats = Appointment.objects.values('status').annotate(count=Count('id'))
    
    # Top performing doctors
    top_doctors = Doctor.objects.annotate(
        appointment_count=Count('appointments'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-appointment_count')[:5]
    
    context = {
        'total_users': total_users,
        'total_doctors': total_doctors,
        'total_appointments': total_appointments,
        'total_reviews': total_reviews,
        'total_checkups': total_checkups,
        'new_users_week': new_users_week,
        'new_doctors_week': new_doctors_week,
        'new_appointments_week': new_appointments_week,
        'critical_alerts': critical_alerts,
        'high_alerts': high_alerts,
        'unread_alerts': unread_alerts,
        'recent_activities': recent_activities,
        'appointment_stats': appointment_stats,
        'top_doctors': top_doctors,
    }
    
    # Log dashboard access
    log_admin_activity(
        admin_user=request.user,
        action_type='read',
        description='Accessed admin dashboard',
        request=request
    )
    
    return render(request, 'admin_system/dashboard.html', context)


class UserManagementView(AdminOnlyMixin, ListView):
    """Comprehensive user management"""
    model = User
    template_name = 'admin_system/user_management.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.filter(is_staff=False).select_related('profile').prefetch_related('appointments')
        
        # Search functionality - support both 'search' and 'q' params
        search = self.request.GET.get('q') or self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Ordering
        order_by = self.request.GET.get('order_by', '-date_joined')
        queryset = queryset.order_by(order_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('q') or self.request.GET.get('search', '')
        context['status'] = self.request.GET.get('status', '')
        context['order_by'] = self.request.GET.get('order_by', '-date_joined')
        
        # Add statistics (always use base counts not filtered)
        context['total_users'] = User.objects.filter(is_staff=False).count()
        context['active_users'] = User.objects.filter(is_staff=False, is_active=True).count()
        context['inactive_users'] = User.objects.filter(is_staff=False, is_active=False).count()
        
        return context


class DoctorManagementView(AdminOnlyMixin, ListView):
    """Comprehensive doctor management"""
    model = Doctor
    template_name = 'admin_system/doctor_management.html'
    context_object_name = 'doctors'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Doctor.objects.select_related('user').prefetch_related('appointments', 'reviews')
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(specialty__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # Filter by specialty
        specialty = self.request.GET.get('specialty')
        if specialty:
            queryset = queryset.filter(specialty=specialty)
        
        # Filter by availability
        availability = self.request.GET.get('availability')
        if availability == 'available':
            queryset = queryset.filter(is_available=True)
        elif availability == 'unavailable':
            queryset = queryset.filter(is_available=False)
        
        # Filter by verification status
        verified = self.request.GET.get('verified')
        if verified == 'verified':
            queryset = queryset.filter(is_verified=True)
        elif verified == 'unverified':
            queryset = queryset.filter(is_verified=False)
        
        # Ordering
        order_by = self.request.GET.get('order_by', '-created_at')
        queryset = queryset.order_by(order_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['specialty'] = self.request.GET.get('specialty', '')
        context['availability'] = self.request.GET.get('availability', '')
        context['verified'] = self.request.GET.get('verified', '')
        context['order_by'] = self.request.GET.get('order_by', '-created_at')
        
        # Add statistics and filter options
        context['specialties_choices'] = Doctor.SPECIALTIES
        context['total_doctors'] = self.get_queryset().count()
        context['verified_doctors'] = Doctor.objects.filter(is_verified=True).count()
        context['available_doctors'] = Doctor.objects.filter(is_available=True).count()
        
        return context


@login_required
@user_passes_test(is_admin)
def system_alerts_view(request):
    """System alerts management"""
    alerts = SystemAlert.objects.order_by('-created_at')
    
    # Filter by type
    alert_type = request.GET.get('type')
    if alert_type:
        alerts = alerts.filter(alert_type=alert_type)
    
    # Filter by severity
    severity = request.GET.get('severity')
    if severity:
        alerts = alerts.filter(severity=severity)
    
    # Filter by status
    status = request.GET.get('status')
    if status == 'unread':
        alerts = alerts.filter(is_read=False)
    elif status == 'unresolved':
        alerts = alerts.filter(is_resolved=False)
    
    # Pagination
    paginator = Paginator(alerts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'alert_types': SystemAlert.ALERT_TYPES,
        'severity_levels': SystemAlert.SEVERITY_LEVELS,
        'selected_type': alert_type,
        'selected_severity': severity,
        'selected_status': status,
    }
    
    return render(request, 'admin_system/system_alerts.html', context)


@require_http_methods(['GET'])
def analytics_view(request):
    """Comprehensive analytics dashboard for system monitoring"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied. Staff privileges required.')
        return redirect('home')
    
    # Get current month data
    now = timezone.now()
    current_month = now.replace(day=1)
    
    # Calculate key metrics
    total_users = User.objects.filter(is_staff=False).count()
    new_users_count = User.objects.filter(
        date_joined__gte=current_month,
        is_staff=False
    ).count()
    existing_users_count = total_users - new_users_count
    
    active_doctors_count = Doctor.objects.filter(is_available=True).count()
    
    total_appointments = Appointment.objects.filter(
        appointment_date__gte=current_month.date()
    ).count()
    
    # Calculate revenue (assuming appointment fee of $100 for demo)
    completed_appointments = Appointment.objects.filter(
        status='completed',
        appointment_date__gte=current_month.date()
    ).count()
    total_revenue = completed_appointments * 100  # Demo calculation
    
    # Get top performing doctors (by appointment count)
    top_doctors = Doctor.objects.annotate(
        appointment_count=Count('appointments')
    ).order_by('-appointment_count')[:5]
    
    # Add demo revenue and rating to doctors
    for doctor in top_doctors:
        doctor.revenue = doctor.appointment_count * 100  # Demo calculation
        doctor.rating = 4.5  # Demo rating
    
    # Appointment status distribution
    appointment_status_data = []
    appointment_status_labels = []
    for status_code, status_label in Appointment.STATUS_CHOICES:
        count = Appointment.objects.filter(status=status_code).count()
        appointment_status_data.append(count)
        appointment_status_labels.append(status_label)
    
    # Revenue data for chart (last 6 months)
    revenue_data = []
    revenue_labels = []
    for i in range(6):
        month_start = (now - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        month_appointments = Appointment.objects.filter(
            status='completed',
            appointment_date__gte=month_start.date(),
            appointment_date__lte=month_end.date()
        ).count()
        revenue_data.append(month_appointments * 100)
        revenue_labels.append(month_start.strftime('%b %Y'))
    
    # Reverse to show oldest to newest
    revenue_data.reverse()
    revenue_labels.reverse()
    
    # Recent system events (alerts)
    recent_events = SystemAlert.objects.order_by('-created_at')[:10]
    
    context = {
        'total_revenue': total_revenue,
        'new_users': new_users_count,
        'existing_users': existing_users_count,
        'total_appointments': total_appointments,
        'active_doctors': active_doctors_count,
        'top_doctors': top_doctors,
        'appointment_status_data': json.dumps(appointment_status_data),
        'appointment_status_labels': json.dumps(appointment_status_labels),
        'revenue_data': json.dumps(revenue_data),
        'revenue_labels': json.dumps(revenue_labels),
        'recent_events': recent_events,
        # Demo system health data
        'server_load': 45,
        'storage_usage': 67,
        'memory_usage': 52,
        'network_usage': 23,
    }
    
    return render(request, 'admin_system/analytics.html', context)


@login_required
@user_passes_test(is_admin)
@require_http_methods(['POST'])
def mark_alert_read(request, alert_id):
    """Mark a system alert as read"""
    try:
        alert = get_object_or_404(SystemAlert, id=alert_id)
        alert.is_read = True
        alert.save(update_fields=['is_read'])
        
        # Log the activity
        log_admin_activity(
            admin_user=request.user,
            action_type='update',
            description=f'Marked alert as read: {alert.title}',
            request=request
        )
        
        return JsonResponse({'success': True, 'message': 'Alert marked as read'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@user_passes_test(is_admin)
@require_http_methods(['POST'])
def mark_alert_resolved(request, alert_id):
    """Mark a system alert as resolved"""
    try:
        alert = get_object_or_404(SystemAlert, id=alert_id)
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.save(update_fields=['is_resolved', 'resolved_at', 'resolved_by'])
        
        # Log the activity
        log_admin_activity(
            admin_user=request.user,
            action_type='update',
            description=f'Resolved alert: {alert.title}',
            request=request
        )
        
        return JsonResponse({'success': True, 'message': 'Alert resolved successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@user_passes_test(is_admin)
def security_monitoring_view(request):
    """Security monitoring dashboard for admin system"""
    today = timezone.now().date()
    
    # Get login activities from admin activities
    login_activities = AdminActivity.objects.filter(
        description__icontains='login'
    ).select_related('admin').order_by('-timestamp')[:20]
    
    # Get security-related statistics
    successful_logins = AdminActivity.objects.filter(
        timestamp__date=today,
        description__icontains='login',
        success=True
    ).count()
    
    failed_logins = AdminActivity.objects.filter(
        timestamp__date=today,
        description__icontains='failed login',
        success=False
    ).count()
    
    # Get security alerts
    security_alerts = SystemAlert.objects.filter(
        alert_type__in=['security', 'login_failed'],
        is_resolved=False
    ).count()
    
    # Get admin activities for the log
    activities = AdminActivity.objects.select_related('admin').order_by('-timestamp')
    
    # Filter by action type if provided
    action_type = request.GET.get('action_type')
    if action_type:
        activities = activities.filter(action_type=action_type)
    
    # Pagination for admin activities
    paginator = Paginator(activities, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'login_activities': login_activities,
        'successful_logins': successful_logins,
        'failed_logins': failed_logins,
        'active_sessions': 0,  # Demo data - would need session tracking
        'security_alerts': security_alerts,
        'admin_activities': page_obj,
        'page_obj': page_obj,
        'blocked_ips': [],  # Demo data - would implement IP blocking
    }
    
    return render(request, 'admin_system/security.html', context)


@login_required
@user_passes_test(is_admin)
def export_activity_log(request):
    """Export admin activity log as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="admin_activity_log.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'Admin User', 'Action Type', 'Description', 
        'IP Address', 'User Agent', 'Success'
    ])
    
    activities = AdminActivity.objects.select_related('admin').order_by('-timestamp')
    
    for activity in activities:
        writer.writerow([
            activity.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            activity.admin.get_full_name() or activity.admin.username,
            activity.get_action_type_display(),
            activity.description,
            activity.ip_address or 'Unknown',
            activity.user_agent or 'Unknown',
            'Success' if activity.success else 'Failed'
        ])
    
    # Log the export activity
    log_admin_activity(
        admin_user=request.user,
        action_type='read',
        description='Exported admin activity log',
        request=request
    )
    
    return response


@login_required
@user_passes_test(is_admin)
@csrf_exempt
def bulk_user_action(request):
    """Handle bulk actions on users"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=400)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return JsonResponse({'error': 'No users selected'}, status=400)
        
        users = User.objects.filter(id__in=user_ids, is_staff=False)
        count = 0
        
        if action == 'activate':
            count = users.update(is_active=True)
            action_desc = 'Bulk activated users'
        elif action == 'deactivate':
            count = users.update(is_active=False)
            action_desc = 'Bulk deactivated users'
        elif action == 'delete':
            count = users.count()
            users.delete()
            action_desc = 'Bulk deleted users'
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
        
        # Log bulk action
        log_admin_activity(
            admin_user=request.user,
            action_type='bulk_action',
            description=f"{action_desc}: {count} users",
            request=request,
            metadata={'action': action, 'count': count}
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{action_desc}: {count} users',
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
@csrf_exempt
def bulk_doctor_action(request):
    """Handle bulk actions on doctors"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=400)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        doctor_ids = data.get('doctor_ids', [])
        
        if not doctor_ids:
            return JsonResponse({'error': 'No doctors selected'}, status=400)
        
        doctors = Doctor.objects.filter(id__in=doctor_ids)
        count = 0
        
        if action == 'verify':
            count = doctors.update(is_verified=True)
            action_desc = 'Bulk verified doctors'
        elif action == 'unverify':
            count = doctors.update(is_verified=False)
            action_desc = 'Bulk unverified doctors'
        elif action == 'activate':
            count = doctors.update(is_available=True)
            action_desc = 'Bulk activated doctors'
        elif action == 'deactivate':
            count = doctors.update(is_available=False)
            action_desc = 'Bulk deactivated doctors'
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
        
        # Log bulk action
        log_admin_activity(
            admin_user=request.user,
            action_type='bulk_action',
            description=f"{action_desc}: {count} doctors",
            request=request,
            metadata={'action': action, 'count': count}
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{action_desc}: {count} doctors',
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
def export_data(request):
    """Export system data to CSV"""
    export_type = request.GET.get('type', 'users')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{export_type}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    if export_type == 'users':
        writer.writerow(['ID', 'Username', 'First Name', 'Last Name', 'Email', 'Date Joined', 'Is Active', 'Appointments Count'])
        users = User.objects.filter(is_staff=False).select_related('profile').prefetch_related('appointments')
        for user in users:
            writer.writerow([
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                user.email,
                user.date_joined.strftime('%Y-%m-%d'),
                'Yes' if user.is_active else 'No',
                user.appointments.count()
            ])
    
    elif export_type == 'doctors':
        writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Specialty', 'Experience', 'Fee', 'Verified', 'Available', 'Appointments Count'])
        doctors = Doctor.objects.all().prefetch_related('appointments')
        for doctor in doctors:
            writer.writerow([
                doctor.id,
                doctor.display_name,
                doctor.email,
                doctor.phone,
                doctor.get_specialty_display(),
                f"{doctor.experience_years} years",
                f"{getattr(settings, 'CURRENCY_SYMBOLS', {}).get(getattr(settings, 'DEFAULT_CURRENCY', 'USD'), '$')}{doctor.consultation_fee}",
                'Yes' if doctor.is_verified else 'No',
                'Yes' if doctor.is_available else 'No',
                doctor.appointments.count()
            ])
    
    elif export_type == 'appointments':
        writer.writerow(['ID', 'Doctor', 'Patient', 'Date', 'Time', 'Status', 'Created At', 'Fee Paid'])
        appointments = Appointment.objects.all().select_related('doctor', 'patient')
        for apt in appointments:
            writer.writerow([
                apt.id,
                apt.doctor.display_name,
                apt.patient.get_full_name() or apt.patient.username,
                apt.appointment_date,
                apt.appointment_time,
                apt.get_status_display(),
                apt.created_at.strftime('%Y-%m-%d %H:%M'),
                f"{getattr(settings, 'CURRENCY_SYMBOLS', {}).get(getattr(settings, 'DEFAULT_CURRENCY', 'USD'), '$')}{apt.fee_charged}" if apt.fee_charged else 'N/A'
            ])
    
    # Log export activity
    log_admin_activity(
        admin_user=request.user,
        action_type='export',
        description=f'Exported {export_type} data to CSV',
        request=request,
        metadata={'export_type': export_type}
    )
    
    return response


class AppointmentDetailView(AdminOnlyMixin, DetailView):
    """View appointment details"""
    model = Appointment
    template_name = 'admin_system/appointment_detail.html'
    context_object_name = 'appointment'
    pk_url_kwarg = 'appointment_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.get_object()
        
        # Add related information
        context['patient_appointments'] = Appointment.objects.filter(
            patient=appointment.patient
        ).exclude(id=appointment.id).order_by('-appointment_date')[:5]
        
        context['doctor_appointments'] = Appointment.objects.filter(
            doctor=appointment.doctor,
            appointment_date=appointment.appointment_date
        ).exclude(id=appointment.id).order_by('appointment_time')[:10]
        
        # Add completed appointments count for patient
        context['patient_completed_appointments'] = appointment.patient.appointments.filter(status='completed').count()
        
        return context


class DoctorDetailView(AdminOnlyMixin, DetailView):
    """View doctor details"""
    model = Doctor
    template_name = 'admin_system/doctor_detail.html'
    context_object_name = 'doctor'
    pk_url_kwarg = 'doctor_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.get_object()
        
        # Add statistics
        context['total_appointments'] = doctor.appointments.count()
        context['completed_appointments'] = doctor.appointments.filter(status='completed').count()
        context['upcoming_appointments'] = doctor.appointments.filter(
            status='scheduled',
            appointment_date__gte=timezone.now().date()
        ).count()
        context['recent_reviews'] = doctor.reviews.order_by('-created_at')[:5]
        context['avg_rating'] = doctor.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Currency info for templates (consistent with other views)
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


@login_required
@user_passes_test(is_admin)
@require_http_methods(['POST'])
def update_appointment_status(request, appointment_id):
    """Update appointment status"""
    try:
        appointment = get_object_or_404(Appointment, id=appointment_id)
        new_status = request.POST.get('status')
        
        if new_status not in dict(Appointment.STATUS_CHOICES):
            return JsonResponse({'success': False, 'message': 'Invalid status'})
        
        old_status = appointment.status
        appointment.status = new_status
        appointment.save()
        
        # Log the activity
        log_admin_activity(
            admin_user=request.user,
            action_type='update',
            description=f'Updated appointment #{appointment.id} status from {old_status} to {new_status}',
            request=request
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'Appointment status updated to {appointment.get_status_display()}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


class DoctorDeleteView(AdminOnlyMixin, DeleteView):
    """Delete doctor"""
    model = Doctor
    pk_url_kwarg = 'doctor_id'
    success_url = reverse_lazy('admin_system:doctor_management')
    
    def delete(self, request, *args, **kwargs):
        doctor = self.get_object()
        doctor_name = doctor.display_name
        
        # Log the activity before deletion
        log_admin_activity(
            admin_user=request.user,
            action_type='delete',
            description=f'Deleted doctor: {doctor_name}',
            request=request
        )
        
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Doctor {doctor_name} deleted successfully!')
        return response


class UserDeleteView(AdminOnlyMixin, DeleteView):
    """Delete user/patient"""
    model = User
    pk_url_kwarg = 'user_id'
    success_url = reverse_lazy('admin_system:user_management')
    
    def get_queryset(self):
        return User.objects.filter(is_staff=False)
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        username = user.username
        
        # Log the activity before deletion
        log_admin_activity(
            admin_user=request.user,
            action_type='delete',
            description=f'Deleted user: {username}',
            request=request
        )
        
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'User {username} deleted successfully!')
        return response


class UserDetailView(AdminOnlyMixin, DetailView):
    """View user/patient details"""
    model = User
    template_name = 'admin_system/user_detail.html'
    context_object_name = 'user_detail'
    pk_url_kwarg = 'user_id'
    
    def get_queryset(self):
        return User.objects.filter(is_staff=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        # Add statistics
        context['total_appointments'] = user.appointments.count()
        context['completed_appointments'] = user.appointments.filter(status='completed').count()
        context['upcoming_appointments'] = user.appointments.filter(
            status='scheduled',
            appointment_date__gte=timezone.now().date()
        ).count()
        context['recent_appointments'] = user.appointments.order_by('-appointment_date')[:10]
        
        return context


class DoctorCreateView(AdminOnlyMixin, CreateView):
    """Create new doctor"""
    model = Doctor
    template_name = 'admin_system/doctor_form.html'
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'specialty',
        'experience_years', 'qualification', 'consultation_fee',
        'bio', 'address', 'city', 'state', 'is_available', 'is_verified'
    ]
    success_url = reverse_lazy('admin_system:doctor_management')
    
    def form_valid(self, form):
        # Create user account first
        user = User.objects.create_user(
            username=f"dr.{form.cleaned_data['first_name'].lower()}.{form.cleaned_data['last_name'].lower()}",
            email=form.cleaned_data['email'],
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
            password='doctor123'  # Default password
        )
        
        # Set the user for the doctor instance
        form.instance.user = user
        
        response = super().form_valid(form)
        
        # Log the activity
        log_admin_activity(
            admin_user=self.request.user,
            action_type='create',
            description=f'Created doctor: {self.object.display_name}',
            request=self.request
        )
        
        messages.success(self.request, f'Doctor {self.object.display_name} created successfully! Default password: doctor123')
        return response


class DoctorUpdateView(AdminOnlyMixin, UpdateView):
    """Update doctor information"""
    model = Doctor
    template_name = 'admin_system/doctor_form.html'
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'specialty',
        'experience_years', 'qualification', 'consultation_fee',
        'bio', 'address', 'city', 'state', 'is_available', 'is_verified'
    ]
    pk_url_kwarg = 'doctor_id'
    success_url = reverse_lazy('admin_system:doctor_management')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Log the activity
        log_admin_activity(
            admin_user=self.request.user,
            action_type='update',
            description=f'Updated doctor: {self.object.display_name}',
            request=self.request
        )
        
        messages.success(self.request, f'Doctor {self.object.display_name} updated successfully!')
        return response


class UserCreateView(AdminOnlyMixin, CreateView):
    """Create new user/patient"""
    model = User
    template_name = 'admin_system/user_form.html'
    fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
    success_url = reverse_lazy('admin_system:user_management')
    
    def form_valid(self, form):
        # Set a default password
        form.instance.set_password('temppass123')
        response = super().form_valid(form)
        
        # Create user profile if doesn't exist
        UserProfile.objects.get_or_create(user=self.object)
        
        # Log the activity
        log_admin_activity(
            admin_user=self.request.user,
            action_type='create',
            description=f'Created user: {self.object.username}',
            request=self.request
        )
        
        messages.success(self.request, f'User {self.object.username} created successfully! Default password: temppass123')
        return response


class UserUpdateView(AdminOnlyMixin, UpdateView):
    """Update user information"""
    model = User
    template_name = 'admin_system/user_form.html'
    fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
    pk_url_kwarg = 'user_id'
    success_url = reverse_lazy('admin_system:user_management')
    
    def get_queryset(self):
        return User.objects.filter(is_staff=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object:
            context['completed_appointments_count'] = self.object.appointments.filter(status='completed').count()
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Log the activity
        log_admin_activity(
            admin_user=self.request.user,
            action_type='update',
            description=f'Updated user: {self.object.username}',
            request=self.request
        )
        
        messages.success(self.request, f'User {self.object.username} updated successfully!')
        return response


class AppointmentManagementView(AdminOnlyMixin, ListView):
    """Comprehensive appointment management"""
    model = Appointment
    template_name = 'admin_system/appointment_management.html'
    context_object_name = 'appointments'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Appointment.objects.select_related('doctor', 'patient').order_by('-created_at')
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(doctor__first_name__icontains=search) |
                Q(doctor__last_name__icontains=search) |
                Q(patient__username__icontains=search) |
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(appointment_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(appointment_date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['status'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Add statistics
        context['appointment_statuses'] = Appointment.STATUS_CHOICES
        context['total_appointments'] = self.get_queryset().count()
        context['appointment_stats'] = Appointment.objects.values('status').annotate(count=Count('id'))
        
        return context
