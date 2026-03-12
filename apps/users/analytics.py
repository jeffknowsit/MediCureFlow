"""
Analytics service for generating dashboard statistics and insights.

This module provides comprehensive analytics functionality for patients, doctors,
and administrators including charts, trends, and performance metrics.
"""

from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from collections import defaultdict
import json

from apps.doctors.models import Doctor, Appointment, Review
from .models import UserProfile


class PatientAnalytics:
    """
    Analytics service for patient dashboard and insights.
    """
    
    def __init__(self, user):
        self.user = user
        self.profile = getattr(user, 'profile', None)
    
    def get_dashboard_stats(self):
        """
        Get comprehensive dashboard statistics for patient.
        """
        appointments = Appointment.objects.filter(patient=self.user)
        
        stats = {
            'total_appointments': appointments.count(),
            'completed_appointments': appointments.filter(status='completed').count(),
            'upcoming_appointments': appointments.filter(
                appointment_date__gte=timezone.now().date()
            ).count(),
            'cancelled_appointments': appointments.filter(status='cancelled').count(),
            'favorite_doctors': self.get_favorite_doctors_count(),
            'total_reviews': Review.objects.filter(patient=self.user).count(),
            'average_rating_given': self.get_average_rating_given(),
            'total_spent': self.calculate_total_spent(),
        }
        
        # Calculate completion rate
        if stats['total_appointments'] > 0:
            stats['completion_rate'] = round(
                (stats['completed_appointments'] / stats['total_appointments']) * 100, 1
            )
        else:
            stats['completion_rate'] = 0
        
        return stats
    
    def get_appointment_trends(self, months=6):
        """
        Get appointment trends over the last N months.
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        appointments = Appointment.objects.filter(
            patient=self.user,
            appointment_date__gte=start_date,
            appointment_date__lte=end_date
        )
        
        # Group by month
        monthly_data = defaultdict(int)
        for appointment in appointments:
            month_key = appointment.appointment_date.strftime('%Y-%m')
            monthly_data[month_key] += 1
        
        # Fill in missing months with zero
        current_date = start_date.replace(day=1)
        chart_data = []
        
        while current_date <= end_date:
            month_key = current_date.strftime('%Y-%m')
            chart_data.append({
                'month': current_date.strftime('%B %Y'),
                'appointments': monthly_data[month_key],
                'date': month_key
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return chart_data
    
    def get_specialty_breakdown(self):
        """
        Get breakdown of appointments by medical specialty.
        """
        appointments = Appointment.objects.filter(
            patient=self.user
        ).select_related('doctor')
        
        specialty_count = defaultdict(int)
        for appointment in appointments:
            specialty = appointment.doctor.get_specialty_display()
            specialty_count[specialty] += 1
        
        return [
            {'specialty': specialty, 'count': count}
            for specialty, count in specialty_count.items()
        ]
    
    def get_recent_activity(self, limit=10):
        """
        Get recent activity feed for the patient.
        """
        activities = []
        
        # Recent appointments
        recent_appointments = Appointment.objects.filter(
            patient=self.user
        ).order_by('-created_at')[:limit]
        
        for appointment in recent_appointments:
            activities.append({
                'type': 'appointment',
                'title': f'Appointment with {appointment.doctor.display_name}',
                'description': f'Scheduled for {appointment.appointment_date} at {appointment.appointment_time}',
                'date': appointment.created_at,
                'icon': 'bi-calendar-plus',
                'status': appointment.status
            })
        
        # Recent reviews
        recent_reviews = Review.objects.filter(
            patient=self.user
        ).order_by('-created_at')[:limit]
        
        for review in recent_reviews:
            activities.append({
                'type': 'review',
                'title': f'Reviewed {review.doctor.display_name}',
                'description': f'Gave {review.rating} stars - {review.title or "No title"}',
                'date': review.created_at,
                'icon': 'bi-star-fill',
                'rating': review.rating
            })
        
        # Sort by date and return top items
        activities.sort(key=lambda x: x['date'], reverse=True)
        return activities[:limit]
    
    def get_favorite_doctors_count(self):
        """
        Get count of favorite doctors (doctors with multiple appointments).
        """
        return Appointment.objects.filter(
            patient=self.user
        ).values('doctor').annotate(
            appointment_count=Count('id')
        ).filter(appointment_count__gte=2).count()
    
    def get_average_rating_given(self):
        """
        Get average rating given by the patient.
        """
        avg_rating = Review.objects.filter(
            patient=self.user
        ).aggregate(avg=Avg('rating'))['avg']
        
        return round(avg_rating, 1) if avg_rating else 0
    
    def calculate_total_spent(self):
        """
        Calculate total amount spent on appointments.
        """
        from decimal import Decimal
        
        total = Appointment.objects.filter(
            patient=self.user,
            status='completed'
        ).aggregate(
            total=Sum('doctor__consultation_fee')
        )['total']
        
        return total or Decimal('0.00')
    
    def get_health_insights(self):
        """
        Get health insights based on appointment history.
        """
        appointments = Appointment.objects.filter(
            patient=self.user
        ).select_related('doctor')
        
        # Most visited specialty
        specialty_visits = defaultdict(int)
        for appointment in appointments:
            specialty_visits[appointment.doctor.specialty] += 1
        
        most_visited = max(specialty_visits.items(), key=lambda x: x[1]) if specialty_visits else None
        
        # Appointment frequency
        total_appointments = appointments.count()
        if total_appointments > 0 and self.profile and self.profile.created_at:
            days_since_registration = (timezone.now() - self.profile.created_at).days
            if days_since_registration > 0:
                avg_appointments_per_month = round((total_appointments / days_since_registration) * 30, 1)
            else:
                avg_appointments_per_month = 0
        else:
            avg_appointments_per_month = 0
        
        return {
            'most_visited_specialty': most_visited[0] if most_visited else None,
            'most_visited_count': most_visited[1] if most_visited else 0,
            'avg_appointments_per_month': avg_appointments_per_month,
            'health_score': self.calculate_health_engagement_score()
        }
    
    def calculate_health_engagement_score(self):
        """
        Calculate a health engagement score based on various factors.
        """
        score = 0
        
        # Points for having appointments
        appointments_count = Appointment.objects.filter(patient=self.user).count()
        score += min(appointments_count * 10, 50)  # Max 50 points
        
        # Points for completing profile
        if self.profile:
            if self.profile.date_of_birth:
                score += 10
            if self.profile.blood_group:
                score += 10
            if self.profile.allergies:
                score += 10
            if self.profile.emergency_contact_name:
                score += 10
        
        # Points for writing reviews
        reviews_count = Review.objects.filter(patient=self.user).count()
        score += min(reviews_count * 5, 25)  # Max 25 points
        
        # Points for profile completeness
        if self.profile and self.profile.profile_picture:
            score += 5
        
        return min(score, 100)  # Cap at 100


class DoctorAnalytics:
    """
    Analytics service for doctor dashboard and performance metrics.
    """
    
    def __init__(self, doctor):
        self.doctor = doctor
    
    def get_dashboard_stats(self):
        """
        Get comprehensive dashboard statistics for doctor.
        """
        appointments = Appointment.objects.filter(doctor=self.doctor)
        reviews = Review.objects.filter(doctor=self.doctor, is_approved=True)
        
        stats = {
            'total_appointments': appointments.count(),
            'completed_appointments': appointments.filter(status='completed').count(),
            'upcoming_appointments': appointments.filter(
                appointment_date__gte=timezone.now().date()
            ).count(),
            'total_patients': appointments.values('patient').distinct().count(),
            'total_reviews': reviews.count(),
            'average_rating': round(reviews.aggregate(avg=Avg('rating'))['avg'] or 0, 1),
            'total_earnings': self.calculate_total_earnings(),
            'monthly_earnings': self.calculate_monthly_earnings(),
        }
        
        # Calculate patient satisfaction rate
        if stats['total_reviews'] > 0:
            satisfied_reviews = reviews.filter(rating__gte=4).count()
            stats['satisfaction_rate'] = round(
                (satisfied_reviews / stats['total_reviews']) * 100, 1
            )
        else:
            stats['satisfaction_rate'] = 0
        
        return stats
    
    def get_appointment_trends(self, months=6):
        """
        Get appointment trends over the last N months.
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        appointments = Appointment.objects.filter(
            doctor=self.doctor,
            appointment_date__gte=start_date,
            appointment_date__lte=end_date
        )
        
        # Group by month and status
        monthly_data = defaultdict(lambda: defaultdict(int))
        for appointment in appointments:
            month_key = appointment.appointment_date.strftime('%Y-%m')
            monthly_data[month_key][appointment.status] += 1
            monthly_data[month_key]['total'] += 1
        
        # Generate chart data
        current_date = start_date.replace(day=1)
        chart_data = []
        
        while current_date <= end_date:
            month_key = current_date.strftime('%Y-%m')
            month_data = monthly_data[month_key]
            
            chart_data.append({
                'month': current_date.strftime('%B %Y'),
                'total': month_data['total'],
                'completed': month_data['completed'],
                'cancelled': month_data['cancelled'],
                'date': month_key
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return chart_data
    
    def get_rating_distribution(self):
        """
        Get distribution of ratings received.
        """
        reviews = Review.objects.filter(doctor=self.doctor, is_approved=True)
        
        rating_counts = {i: 0 for i in range(1, 6)}
        for review in reviews:
            rating_counts[review.rating] += 1
        
        return [
            {'rating': rating, 'count': count}
            for rating, count in rating_counts.items()
        ]
    
    def get_peak_hours(self):
        """
        Get peak appointment hours.
        """
        appointments = Appointment.objects.filter(doctor=self.doctor)
        
        hour_counts = defaultdict(int)
        for appointment in appointments:
            hour = appointment.appointment_time.hour
            hour_counts[hour] += 1
        
        return [
            {'hour': f'{hour:02d}:00', 'count': count}
            for hour, count in sorted(hour_counts.items())
        ]
    
    def calculate_total_earnings(self):
        """
        Calculate total earnings from completed appointments.
        """
        from decimal import Decimal
        
        completed_appointments = Appointment.objects.filter(
            doctor=self.doctor,
            status='completed'
        )
        
        # Calculate actual earnings from fee_charged
        total_earnings = sum(
            apt.fee_charged or self.doctor.consultation_fee 
            for apt in completed_appointments
        )
        
        return total_earnings
    
    def calculate_monthly_earnings(self):
        """
        Calculate current month's earnings.
        """
        from decimal import Decimal
        
        current_month = timezone.now().date().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        monthly_appointments = Appointment.objects.filter(
            doctor=self.doctor,
            status='completed',
            appointment_date__gte=current_month,
            appointment_date__lt=next_month
        )
        
        # Calculate actual earnings from fee_charged
        total_earnings = sum(
            apt.fee_charged or self.doctor.consultation_fee 
            for apt in monthly_appointments
        )
        
        return total_earnings
    
    def get_patient_demographics(self):
        """
        Get patient demographics breakdown.
        """
        appointments = Appointment.objects.filter(
            doctor=self.doctor
        ).select_related('patient__profile')
        
        age_groups = defaultdict(int)
        gender_counts = defaultdict(int)
        
        for appointment in appointments:
            profile = getattr(appointment.patient, 'profile', None)
            if profile:
                # Age groups
                if profile.age:
                    if profile.age < 18:
                        age_groups['Under 18'] += 1
                    elif profile.age < 30:
                        age_groups['18-29'] += 1
                    elif profile.age < 50:
                        age_groups['30-49'] += 1
                    elif profile.age < 65:
                        age_groups['50-64'] += 1
                    else:
                        age_groups['65+'] += 1
                
                # Gender
                if profile.gender:
                    gender_display = dict(UserProfile.GENDER_CHOICES).get(profile.gender, 'Unknown')
                    gender_counts[gender_display] += 1
        
        return {
            'age_groups': [{'group': group, 'count': count} for group, count in age_groups.items()],
            'gender_distribution': [{'gender': gender, 'count': count} for gender, count in gender_counts.items()]
        }
    
    def get_revenue_trends(self, months=6):
        """
        Get revenue trends over the last N months.
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        appointments = Appointment.objects.filter(
            doctor=self.doctor,
            status='completed',
            appointment_date__gte=start_date,
            appointment_date__lte=end_date
        )
        
        monthly_revenue = defaultdict(float)
        for appointment in appointments:
            month_key = appointment.appointment_date.strftime('%Y-%m')
            # Using fee_charged or falling back to consultation_fee
            fee = float(appointment.fee_charged or self.doctor.consultation_fee or 0)
            monthly_revenue[month_key] += fee
        
        # Generate chart data
        current_date = start_date.replace(day=1)
        chart_data = []
        
        while current_date <= end_date:
            month_key = current_date.strftime('%Y-%m')
            chart_data.append({
                'month': current_date.strftime('%b %Y'),
                'revenue': monthly_revenue[month_key],
                'date': month_key
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return chart_data

    def calculate_total_earnings(self):
        """
        Calculate total lifetime earnings.
        """
        from django.db.models import Sum
        total = Appointment.objects.filter(
            doctor=self.doctor,
            status='completed'
        ).aggregate(
            total_sum=Sum('fee_charged')
        )['total_sum'] or 0
        
        if not total:
            # Fallback if fee_charged is not used reliably
            count = Appointment.objects.filter(doctor=self.doctor, status='completed').count()
            total = count * float(self.doctor.consultation_fee or 0)
            
        return float(total)

    def calculate_revenue_performance(self):
        """
        Calculate revenue performance compared to last month.
        """
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        this_month_revenue = float(self.calculate_monthly_earnings())
        
        last_month_appointments = Appointment.objects.filter(
            doctor=self.doctor,
            status='completed',
            appointment_date__gte=last_month_start,
            appointment_date__lte=last_month_end
        )
        
        last_month_revenue = sum(
            float(apt.fee_charged or self.doctor.consultation_fee or 0)
            for apt in last_month_appointments
        )
        
        growth = 0
        if last_month_revenue > 0:
            growth = ((this_month_revenue - last_month_revenue) / last_month_revenue) * 100
        elif this_month_revenue > 0:
            growth = 100
            
        return {
            'this_month': this_month_revenue,
            'last_month': last_month_revenue,
            'growth_percent': round(growth, 1),
            'trend': 'up' if growth >= 0 else 'down'
        }


class SystemAnalytics:
    """
    Analytics service for system-wide statistics and admin insights.
    """
    
    @staticmethod
    def get_overview_stats():
        """
        Get system overview statistics.
        """
        return {
            'total_users': User.objects.count(),
            'total_doctors': Doctor.objects.count(),
            'active_doctors': Doctor.objects.filter(is_available=True).count(),
            'total_appointments': Appointment.objects.count(),
            'completed_appointments': Appointment.objects.filter(status='completed').count(),
            'total_reviews': Review.objects.filter(is_approved=True).count(),
            'average_rating': round(
                Review.objects.filter(is_approved=True).aggregate(
                    avg=Avg('rating')
                )['avg'] or 0, 1
            ),
            'new_users_this_month': SystemAnalytics.get_new_users_this_month(),
            'appointments_this_month': SystemAnalytics.get_appointments_this_month(),
        }
    
    @staticmethod
    def get_new_users_this_month():
        """
        Get count of new users registered this month.
        """
        current_month = timezone.now().date().replace(day=1)
        return User.objects.filter(date_joined__gte=current_month).count()
    
    @staticmethod
    def get_appointments_this_month():
        """
        Get count of appointments scheduled this month.
        """
        current_month = timezone.now().date().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        return Appointment.objects.filter(
            appointment_date__gte=current_month,
            appointment_date__lt=next_month
        ).count()
    
    @staticmethod
    def get_growth_trends(months=12):
        """
        Get user and appointment growth trends.
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        # User registrations by month
        users = User.objects.filter(date_joined__gte=start_date)
        user_monthly = defaultdict(int)
        
        for user in users:
            month_key = user.date_joined.strftime('%Y-%m')
            user_monthly[month_key] += 1
        
        # Appointments by month
        appointments = Appointment.objects.filter(created_at__gte=start_date)
        appointment_monthly = defaultdict(int)
        
        for appointment in appointments:
            month_key = appointment.created_at.strftime('%Y-%m')
            appointment_monthly[month_key] += 1
        
        # Generate chart data
        chart_data = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            month_key = current_date.strftime('%Y-%m')
            chart_data.append({
                'month': current_date.strftime('%B %Y'),
                'users': user_monthly[month_key],
                'appointments': appointment_monthly[month_key],
                'date': month_key
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return chart_data
    
    @staticmethod
    def get_popular_specialties():
        """
        Get most popular medical specialties.
        """
        specialties = Appointment.objects.values(
            'doctor__specialty'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return [
            {
                'specialty': dict(Doctor.SPECIALTIES).get(item['doctor__specialty'], item['doctor__specialty']),
                'count': item['count']
            }
            for item in specialties
        ]
