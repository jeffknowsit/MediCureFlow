from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils.html import format_html
from .models import Doctor, DoctorAvailability, Appointment, Review, Medication, TestReport


class MedicationInline(admin.TabularInline):
    model = Medication
    extra = 0


class TestReportInline(admin.TabularInline):
    model = TestReport
    extra = 0


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = [
        'photo_thumbnail', 'display_name', 'specialty_badge', 'location', 
        'consultation_fee_display', 'experience_badge', 'availability_status',
        'ratings_summary', 'total_appointments', 'verification_status', 'created_at'
    ]
    list_filter = [
        'specialty', 'city', 'state', 'is_available', 'is_verified', 
        'experience_years', 'created_at', 'consultation_fee'
    ]
    search_fields = [
        'first_name', 'last_name', 'email', 'phone', 'user__username',
        'qualification', 'bio', 'medical_license_number'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'photo_preview', 'statistics_summary',
        'recent_appointments', 'profile_completion'
    ]
    list_select_related = ['user']
    list_per_page = 25
    
    fieldsets = (
        ('Photo Preview', {
            'fields': ('photo_preview',),
            'classes': ('wide',)
        }),
        ('Personal Information', {
            'fields': ('user', 'first_name', 'last_name', 'email', 'phone')
        }),
        ('Professional Information', {
            'fields': (
                'specialty', 'qualification', 'experience_years', 
                'consultation_fee', 'medical_license_number', 'is_verified'
            )
        }),
        ('Extended Professional Info', {
            'fields': ('languages', 'certifications', 'awards'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('state', 'city', 'address')
        }),
        ('Profile & Media', {
            'fields': ('photo', 'bio', 'social_media_links', 'is_available')
        }),
        ('Statistics', {
            'fields': ('statistics_summary', 'recent_appointments', 'profile_completion'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def photo_thumbnail(self, obj):
        """Display small photo thumbnail in list view"""
        if obj.photo:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;" />',
                obj.photo_url
            )
        return format_html(
            '<div style="width: 40px; height: 40px; border-radius: 50%; background: #007bff; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">{}</div>',
            obj.first_name[:1] + obj.last_name[:1] if obj.first_name and obj.last_name else 'DR'
        )
    photo_thumbnail.short_description = 'Photo'
    
    def photo_preview(self, obj):
        """Display larger photo preview in detail view"""
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.photo_url
            )
        return "No photo uploaded"
    photo_preview.short_description = 'Photo Preview'
    
    def specialty_badge(self, obj):
        """Display specialty as colored badge"""
        colors = {
            'cardiology': '#e74c3c',
            'dermatology': '#3498db',
            'pediatrics': '#9b59b6',
            'orthopedics': '#f39c12',
            'neurosurgery': '#2ecc71',
            'general': '#95a5a6',
        }
        color = colors.get(obj.specialty, '#34495e')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_specialty_display()
        )
    specialty_badge.short_description = 'Specialty'
    
    def location(self, obj):
        """Display location with icon"""
        if obj.city and obj.state:
            return format_html(
                '<span title="{}, {}">🌍 {}</span>',
                obj.city, obj.state, obj.city
            )
        return '-'
    location.short_description = 'Location'
    
    def consultation_fee_display(self, obj):
        """Display fee with currency symbol based on DEFAULT_CURRENCY setting"""
        if obj.consultation_fee:
            from django.conf import settings
            currency = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
            currency_symbols = getattr(settings, 'CURRENCY_SYMBOLS', {
                'USD': '$',
                'INR': '₹',
                'EUR': '€',
                'GBP': '£'
            })
            
            symbol = currency_symbols.get(currency, '$')
            return format_html('<strong>{}{}</strong>', symbol, obj.consultation_fee)
        return '-'
    consultation_fee_display.short_description = 'Fee'
    consultation_fee_display.admin_order_field = 'consultation_fee'
    
    def experience_badge(self, obj):
        """Display experience as badge"""
        years = obj.experience_years
        if years >= 20:
            color = '#2ecc71'  # Green for very experienced
        elif years >= 10:
            color = '#f39c12'  # Orange for experienced
        elif years >= 5:
            color = '#3498db'  # Blue for moderately experienced
        else:
            color = '#95a5a6'  # Gray for new
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 8px; font-size: 10px;">{} yrs</span>',
            color, years
        )
    experience_badge.short_description = 'Experience'
    experience_badge.admin_order_field = 'experience_years'
    
    def availability_status(self, obj):
        """Display availability with colored indicator"""
        if obj.is_available:
            return format_html('<span style="color: #2ecc71; font-weight: bold;">● Available</span>')
        return format_html('<span style="color: #e74c3c; font-weight: bold;">● Offline</span>')
    availability_status.short_description = 'Status'
    availability_status.admin_order_field = 'is_available'
    
    def verification_status(self, obj):
        """Display verification status"""
        if obj.is_verified:
            return format_html('<span style="color: #2ecc71; font-weight: bold;">✓ Verified</span>')
        return format_html('<span style="color: #e74c3c;">⚠ Unverified</span>')
    verification_status.short_description = 'Verified'
    verification_status.admin_order_field = 'is_verified'
    
    def ratings_summary(self, obj):
        """Display average rating with stars"""
        try:
            avg_rating = obj.average_rating or 0
            full_stars = int(avg_rating)
            stars = '⭐' * full_stars + '☆' * (5 - full_stars)
            return format_html(
                '<span title="Average: {:.1f}/5">{}</span>',
                avg_rating, stars
            )
        except:
            return '☆☆☆☆☆'
    ratings_summary.short_description = 'Rating'
    
    def total_appointments(self, obj):
        """Display total appointments count"""
        try:
            count = obj.appointments.count()
            return format_html(
                '<span style="background: #ecf0f1; padding: 2px 6px; border-radius: 6px; font-size: 11px;">{}</span>',
                count
            )
        except:
            return '0'
    total_appointments.short_description = 'Appointments'
    
    def statistics_summary(self, obj):
        """Display comprehensive statistics"""
        try:
            appointments = obj.appointments.count()
            completed = obj.appointments.filter(status='completed').count()
            reviews = obj.reviews.count()
            avg_rating = obj.average_rating or 0
            
            return format_html(
                '''
                <div style="background: #f8f9fa; padding: 10px; border-radius: 6px; font-size: 12px;">
                    <strong>📊 Statistics Summary</strong><br/>
                    • Total Appointments: {}<br/>
                    • Completed: {}<br/>
                    • Reviews: {}<br/>
                    • Average Rating: {:.1f}/5<br/>
                    • Success Rate: {:.1f}%
                </div>
                ''',
                appointments, completed, reviews, avg_rating,
                (completed / appointments * 100) if appointments > 0 else 0
            )
        except:
            return "Statistics not available"
    statistics_summary.short_description = 'Statistics'
    
    def recent_appointments(self, obj):
        """Display recent appointments"""
        try:
            recent = obj.appointments.order_by('-created_at')[:3]
            if not recent:
                return "No recent appointments"
            
            appointments_html = "<div style='font-size: 11px;'><strong>Recent Appointments:</strong><br/>"
            for apt in recent:
                appointments_html += f"• {apt.appointment_date} - {apt.patient.get_full_name() or apt.patient.username}<br/>"
            appointments_html += "</div>"
            
            return format_html(appointments_html)
        except:
            return "Unable to load appointments"
    recent_appointments.short_description = 'Recent Activity'
    
    def profile_completion(self, obj):
        """Display profile completion percentage"""
        fields = [
            obj.photo, obj.bio, obj.qualification, obj.experience_years,
            obj.consultation_fee, obj.address, obj.phone
        ]
        completed = sum(1 for field in fields if field)
        percentage = (completed / len(fields)) * 100
        
        if percentage >= 80:
            color = '#2ecc71'
        elif percentage >= 60:
            color = '#f39c12'
        else:
            color = '#e74c3c'
        
        return format_html(
            '<div style="width: 100px; background: #ecf0f1; border-radius: 10px; padding: 2px;"><div style="width: {}%; background: {}; height: 8px; border-radius: 8px;"></div></div><small>{:.0f}% Complete</small>',
            percentage, color, percentage
        )
    profile_completion.short_description = 'Profile Completion'
    
    actions = ['mark_as_verified', 'mark_as_unverified', 'toggle_availability']
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} doctors marked as verified.')
    mark_as_verified.short_description = "Mark selected doctors as verified"
    
    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} doctors marked as unverified.')
    mark_as_unverified.short_description = "Mark selected doctors as unverified"
    
    def toggle_availability(self, request, queryset):
        for doctor in queryset:
            doctor.is_available = not doctor.is_available
            doctor.save()
        self.message_user(request, f'Toggled availability for {queryset.count()} doctors.')
    toggle_availability.short_description = "Toggle availability status"


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'get_day_of_week_display', 'start_time', 'end_time', 'is_active']
    list_filter = ['day_of_week', 'is_active']
    search_fields = ['doctor__first_name', 'doctor__last_name']
    list_select_related = ['doctor']
    list_per_page = 25


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'doctor', 'appointment_date', 'appointment_time', 'status', 'is_paid']
    list_filter = ['status', 'appointment_date', 'is_paid', 'created_at']
    search_fields = ['patient__username', 'doctor__first_name', 'doctor__last_name']
    readonly_fields = ['created_at', 'updated_at', 'fee_charged']
    list_select_related = ['doctor', 'patient']
    list_per_page = 25
    date_hierarchy = 'appointment_date'
    
    fieldsets = (
        ('Appointment Details', {
            'fields': ('doctor', 'patient', 'appointment_date', 'appointment_time', 'duration_minutes')
        }),
        ('Status & Payment', {
            'fields': ('status', 'fee_charged', 'is_paid')
        }),
        ('Notes', {
            'fields': ('patient_notes', 'doctor_notes')
        }),
        ('Contact Backup', {
            'fields': ('patient_phone', 'patient_email'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['patient', 'doctor', 'rating', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['patient__username', 'doctor__first_name', 'doctor__last_name', 'title']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['doctor', 'patient', 'appointment']
    list_per_page = 25
