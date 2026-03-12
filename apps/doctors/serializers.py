"""
Serializers for the doctors app API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Doctor, Appointment, DoctorAvailability, Review
from apps.users.serializers import UserPublicSerializer
# from MediCureFlow.middleware.security import InputSanitizationMixin
from drf_spectacular.utils import extend_schema_field


class DoctorSerializer(serializers.ModelSerializer):
    """Serializer for Doctor model."""
    
    user = UserPublicSerializer(read_only=True)
    display_name = serializers.CharField(read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Doctor
        fields = [
            'id', 'user', 'display_name', 'first_name', 'last_name', 'specialty',
            'qualification', 'experience_years', 'phone', 'email',
            'address', 'city', 'state', 'consultation_fee', 'photo', 'bio',
            'is_available', 'average_rating', 'total_reviews', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_available']
    
    @extend_schema_field(serializers.FloatField)
    def get_average_rating(self, obj):
        """Calculate average rating for the doctor."""
        # Use prefetched reviews if available to avoid N+1 queries
        if hasattr(obj, '_prefetched_objects_cache') and 'reviews' in obj._prefetched_objects_cache:
            reviews = obj._prefetched_objects_cache['reviews']
            if reviews:
                return round(sum(review.rating for review in reviews) / len(reviews), 1)
            return 0
        else:
            # Fallback to database query if not prefetched
            reviews = obj.reviews.all()
            if reviews.exists():
                return round(sum(review.rating for review in reviews) / reviews.count(), 1)
            return 0
    
    @extend_schema_field(serializers.IntegerField)
    def get_total_reviews(self, obj):
        """Get total number of reviews for the doctor."""
        # Use prefetched reviews if available to avoid N+1 queries
        if hasattr(obj, '_prefetched_objects_cache') and 'reviews' in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache['reviews'])
        else:
            # Fallback to database query if not prefetched
            return obj.reviews.count()


class DoctorDetailSerializer(DoctorSerializer):
    """Extended serializer for doctor detail view with additional information."""
    
    recent_reviews = serializers.SerializerMethodField()
    availability_today = serializers.SerializerMethodField()
    
    class Meta(DoctorSerializer.Meta):
        fields = DoctorSerializer.Meta.fields + ['recent_reviews', 'availability_today']
    
    @extend_schema_field(serializers.ListField)
    def get_recent_reviews(self, obj):
        """Get recent reviews for the doctor."""
        reviews = Review.objects.filter(doctor=obj).order_by('-created_at')[:3]
        return ReviewSerializer(reviews, many=True).data
    
    @extend_schema_field(serializers.DictField)
    def get_availability_today(self, obj):
        """Get today's availability for the doctor."""
        from django.utils import timezone
        today = timezone.now().date()
        day_of_week = today.weekday()
        availability = DoctorAvailability.objects.filter(
            doctor=obj,
            day_of_week=day_of_week,
            is_active=True
        ).first()
        if availability:
            return DoctorAvailabilitySerializer(availability).data
        return None


class DoctorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating doctor profile."""
    
    class Meta:
        model = Doctor
        fields = [
            'first_name', 'last_name', 'specialty', 'qualification',
            'experience_years', 'phone', 'email', 'address', 'city',
            'state', 'consultation_fee', 'photo', 'bio'
        ]
    
    def create(self, validated_data):
        """Create doctor with logged-in user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_consultation_fee(self, value):
        """Validate consultation fee."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative.")
        return value
    
    def validate_experience_years(self, value):
        """Validate experience years."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Experience years cannot be negative.")
        if value is not None and value > 60:
            raise serializers.ValidationError("Experience years seems too high.")
        return value
    
    def validate_photo(self, value):
        """Validate doctor photo upload."""
        is_valid, error_message = self.validate_file_upload(value)
        if not is_valid:
            raise serializers.ValidationError(error_message)
        return value
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Convert to mutable dict if QueryDict
        if hasattr(data, '_mutable') and not data._mutable:
            data = data.copy()
        else:
            data = dict(data)
        
        # Sanitize text fields
        text_fields = ['first_name', 'last_name', 'specialty', 'qualification',
                      'address', 'city', 'state', 'bio']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = self.sanitize_html_input(data[field])
        
        return super().to_internal_value(data)


class DoctorUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating doctor profile."""
    
    class Meta:
        model = Doctor
        fields = [
            'first_name', 'last_name', 'specialty', 'qualification',
            'experience_years', 'phone', 'email', 'address', 'city',
            'state', 'consultation_fee', 'photo', 'bio'
        ]
    
    def validate_consultation_fee(self, value):
        """Validate consultation fee."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative.")
        return value
    
    def validate_experience_years(self, value):
        """Validate experience years."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Experience years cannot be negative.")
        if value is not None and value > 60:
            raise serializers.ValidationError("Experience years seems too high.")
        return value
    
    def validate_photo(self, value):
        """Validate doctor photo upload."""
        is_valid, error_message = self.validate_file_upload(value)
        if not is_valid:
            raise serializers.ValidationError(error_message)
        return value
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Convert to mutable dict if QueryDict
        if hasattr(data, '_mutable') and not data._mutable:
            data = data.copy()
        else:
            data = dict(data)
        
        # Sanitize text fields
        text_fields = ['first_name', 'last_name', 'specialty', 'qualification',
                      'address', 'city', 'state', 'bio']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = self.sanitize_html_input(data[field])
        
        return super().to_internal_value(data)


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for Appointment model."""
    
    doctor = DoctorSerializer(read_only=True)
    patient = UserPublicSerializer(read_only=True)
    doctor_id = serializers.IntegerField(write_only=True)
    patient_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'doctor', 'patient', 'appointment_date', 'appointment_time',
            'duration_minutes', 'status', 'patient_notes', 'doctor_notes',
            'patient_phone', 'patient_email', 'fee_charged', 'is_paid',
            'created_at', 'updated_at', 'doctor_id', 'patient_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create appointment with logged-in user as patient if not specified."""
        if 'patient_id' not in validated_data:
            validated_data['patient_id'] = self.context['request'].user.id
        return super().create(validated_data)
    
    def validate(self, attrs):
        """Validate appointment data."""
        from django.utils import timezone
        
        naive_datetime = timezone.datetime.combine(
            attrs['appointment_date'],
            attrs['appointment_time']
        )
        appointment_datetime = timezone.make_aware(naive_datetime)
        
        # Check if appointment is in the future
        if appointment_datetime <= timezone.now():
            raise serializers.ValidationError("Appointment must be scheduled for a future time.")
        
        # Check doctor availability
        doctor_id = attrs.get('doctor_id')
        if doctor_id:
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                if not doctor.is_available:
                    raise serializers.ValidationError("Doctor is not currently available for appointments.")
            except Doctor.DoesNotExist:
                raise serializers.ValidationError("Doctor does not exist.")
        
        return attrs
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Convert to mutable dict if QueryDict
        if hasattr(data, '_mutable') and not data._mutable:
            data = data.copy()
        else:
            data = dict(data)
        
        # Sanitize text fields
        text_fields = ['patient_notes', 'doctor_notes', 'patient_phone', 'patient_email']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = self.sanitize_html_input(data[field])
        
        return super().to_internal_value(data)


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating appointment status and notes."""
    
    class Meta:
        model = Appointment
        fields = ['status', 'patient_notes', 'doctor_notes']
    
    def validate_status(self, value):
        """Validate status transitions."""
        if self.instance:
            current_status = self.instance.status
            # Define allowed status transitions
            allowed_transitions = {
                'scheduled': ['confirmed', 'cancelled'],
                'confirmed': ['completed', 'cancelled'],
                'completed': [],  # No transitions from completed
                'cancelled': []   # No transitions from cancelled
            }
            
            if value not in allowed_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Cannot change status from {current_status} to {value}"
                )
        return value


class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for DoctorAvailability model."""
    
    class Meta:
        model = DoctorAvailability
        fields = [
            'id', 'doctor', 'day_of_week', 'start_time', 'end_time',
            'is_active'
        ]
        read_only_fields = ['id']


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model."""
    
    patient = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'doctor', 'patient', 'appointment', 'rating',
            'comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'patient', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create review with logged-in user as patient."""
        validated_data['patient'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_rating(self, value):
        """Validate rating value."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def validate(self, attrs):
        """Validate review data."""
        # Check if user has had an appointment with this doctor
        patient = self.context['request'].user
        doctor = attrs.get('doctor')
        
        if doctor and not Appointment.objects.filter(
            patient=patient,
            doctor=doctor,
            status='completed'
        ).exists():
            raise serializers.ValidationError(
                "You can only review doctors you have had completed appointments with."
            )
        
        # Check if user has already reviewed this doctor
        if doctor and Review.objects.filter(
            patient=patient,
            doctor=doctor
        ).exists():
            raise serializers.ValidationError(
                "You have already reviewed this doctor."
            )
        
        return attrs
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Convert to mutable dict if QueryDict
        if hasattr(data, '_mutable') and not data._mutable:
            data = data.copy()
        else:
            data = dict(data)
        
        # Sanitize comment field
        if 'comment' in data and data['comment']:
            # data['comment'] = self.sanitize_html_input(data['comment'])
            pass
        
        return super().to_internal_value(data)


class DoctorSearchSerializer(serializers.Serializer):
    """Serializer for doctor search parameters."""
    
    q = serializers.CharField(required=False, help_text="Search by doctor name")
    specialty = serializers.CharField(required=False, help_text="Filter by specialty")
    city = serializers.CharField(required=False, help_text="Filter by city")
    state = serializers.CharField(required=False, help_text="Filter by state")
    min_experience = serializers.IntegerField(required=False, help_text="Minimum years of experience")
    max_fee = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, help_text="Maximum consultation fee")
    gender = serializers.CharField(required=False, help_text="Filter by gender")
    languages = serializers.CharField(required=False, help_text="Filter by languages spoken")
    available_only = serializers.BooleanField(default=False, help_text="Show only available doctors")
    ordering = serializers.CharField(required=False, help_text="Order by: rating, experience, fee_low, fee_high")


class AppointmentBookingSerializer(serializers.ModelSerializer):
    """Simplified serializer for booking appointments."""
    
    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'appointment_time', 'patient_notes']
    
    def create(self, validated_data):
        """Create appointment with logged-in user as patient."""
        validated_data['patient'] = self.context['request'].user
        validated_data['status'] = 'scheduled'
        return super().create(validated_data)
    
    def validate(self, attrs):
        """Validate booking data."""
        from django.utils import timezone
        
        # Check if appointment is in the future
        naive_datetime = timezone.datetime.combine(
            attrs['appointment_date'],
            attrs['appointment_time']
        )
        appointment_datetime = timezone.make_aware(naive_datetime)
        
        if appointment_datetime <= timezone.now():
            raise serializers.ValidationError("Appointment must be scheduled for a future time.")
        
        # Check if doctor is available at this time
        doctor = attrs.get('doctor')
        appointment_date = attrs.get('appointment_date')
        appointment_time = attrs.get('appointment_time')
        
        # Check for conflicting appointments
        conflicts = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status__in=['scheduled', 'confirmed']
        )
        
        if conflicts.exists():
            raise serializers.ValidationError(
                "This time slot is already booked. Please choose a different time."
            )
        
        return attrs
