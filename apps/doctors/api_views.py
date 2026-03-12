"""
API ViewSets for the doctors app.
"""

from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg
from django.utils import timezone
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Doctor, Appointment, DoctorAvailability, Review
from .serializers import (
    DoctorSerializer, DoctorDetailSerializer, DoctorCreateSerializer, DoctorUpdateSerializer,
    AppointmentSerializer, AppointmentUpdateSerializer, AppointmentBookingSerializer,
    DoctorAvailabilitySerializer, ReviewSerializer, DoctorSearchSerializer
)


@extend_schema_view(
    list=extend_schema(description="List all doctors with search and filtering"),
    retrieve=extend_schema(description="Get detailed doctor information"),
    create=extend_schema(description="Create doctor profile (admin only)"),
    update=extend_schema(description="Update doctor profile"),
    partial_update=extend_schema(description="Partially update doctor profile"),
    destroy=extend_schema(description="Delete doctor profile (admin only)"),
)
class DoctorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing doctors.
    """
    queryset = Doctor.objects.select_related('user').prefetch_related('reviews', 'availability_slots')
    serializer_class = DoctorSerializer
    permission_classes = [permissions.AllowAny]  # Allow public access for browsing doctors
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'specialty', 'bio']
    ordering_fields = ['experience_years', 'consultation_fee', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return DoctorCreateSerializer
        elif self.action == 'retrieve':
            return DoctorDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return DoctorUpdateSerializer
        return DoctorSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['create', 'destroy']:
            # Only admin can create/delete doctors
            permission_classes = [permissions.IsAdminUser]
        elif self.action in ['update', 'partial_update']:
            # Only the doctor themselves or admin can update
            permission_classes = [permissions.IsAuthenticated]
        else:
            # Allow public access for listing and viewing doctors
            permission_classes = [permissions.AllowAny]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter and search doctors based on query parameters."""
        queryset = Doctor.objects.select_related('user').prefetch_related(
            'reviews', 'availability_slots'
        )
        
        # Search filters
        q = self.request.query_params.get('q', None)
        if q:
            queryset = queryset.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(specialty__icontains=q) |
                Q(bio__icontains=q)
            )
        
        # Specialty filter
        specialty = self.request.query_params.get('specialty', None)
        if specialty:
            queryset = queryset.filter(specialty=specialty)
        
        # Location filters
        city = self.request.query_params.get('city', None)
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        state = self.request.query_params.get('state', None)
        if state:
            queryset = queryset.filter(state__icontains=state)
        
        # Experience filter
        min_experience = self.request.query_params.get('min_experience', None)
        if min_experience:
            try:
                min_exp = int(min_experience)
                queryset = queryset.filter(experience_years__gte=min_exp)
            except ValueError:
                pass
        
        # Consultation fee filter
        max_fee = self.request.query_params.get('max_fee', None)
        if max_fee:
            try:
                max_fee_val = float(max_fee)
                queryset = queryset.filter(consultation_fee__lte=max_fee_val)
            except (ValueError, TypeError):
                pass
        
        # Available only filter
        available_only = self.request.query_params.get('available_only', 'false').lower()
        if available_only == 'true':
            queryset = queryset.filter(is_available=True)
        
        
        return queryset
    
    def perform_update(self, serializer):
        """Ensure only the doctor or admin can update."""
        doctor = self.get_object()
        user = self.request.user
        
        if doctor.user != user and not user.is_staff:
            raise PermissionDenied("You can only update your own profile.")
        
        serializer.save()
    
    @extend_schema(
        description="Search doctors with advanced filters",
        parameters=[DoctorSearchSerializer],
        responses={200: DoctorSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced doctor search endpoint."""
        queryset = self.get_queryset()
        
        # Apply ordering
        ordering = request.query_params.get('ordering', None)
        if ordering == 'rating':
            # Order by average rating (requires calculation)
            queryset = queryset.annotate(
                avg_rating=Avg('reviews__rating')
            ).order_by('-avg_rating')
        elif ordering == 'experience':
            queryset = queryset.order_by('-experience_years')
        elif ordering == 'fee_low':
            queryset = queryset.order_by('consultation_fee')
        elif ordering == 'fee_high':
            queryset = queryset.order_by('-consultation_fee')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get doctor's available time slots for a specific date",
        responses={200: {"type": "array", "items": {"type": "string"}}}
    )
    @action(detail=True, methods=['get'])
    def available_slots(self, request, pk=None):
        """Get available time slots for a doctor on a specific date."""
        doctor = self.get_object()
        date_param = request.query_params.get('date', None)
        
        if not date_param:
            return Response(
                {'error': 'Date parameter is required (YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get doctor's availability for the day of week
        day_of_week = date.weekday()
        availability = DoctorAvailability.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_active=True
        ).first()
        
        if not availability:
            return Response([])
        
        # Generate time slots (example: every 30 minutes)
        from datetime import time, timedelta, datetime
        
        slots = []
        current_time = datetime.combine(date, availability.start_time)
        end_time = datetime.combine(date, availability.end_time)
        
        while current_time < end_time:
            # Check if this slot is already booked
            booked = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date,
                appointment_time=current_time.time(),
                status__in=['scheduled', 'confirmed']
            ).exists()
            
            if not booked:
                slots.append(current_time.strftime('%H:%M'))
            
            current_time += timedelta(minutes=30)
        
        return Response(slots)
    
    @extend_schema(
        description="Get list of available specialties",
        responses={200: {"type": "array", "items": {"type": "object"}}}
    )
    @action(detail=False, methods=['get'])
    def specialties(self, request):
        """Get cached list of doctor specialties."""
        cache_key = f"{getattr(settings, 'CACHE_KEY_PREFIX', 'MediCureFlow')}:doctor_specialties"
        specialties = cache.get(cache_key)
        
        if specialties is None:
            # Get unique specialties from database
            from .models import Doctor
            specialty_choices = Doctor.SPECIALTIES
            specialties = [
                {'value': choice[0], 'label': choice[1]} 
                for choice in specialty_choices
            ]
            # Cache for 1 hour since specialties rarely change
            cache.set(cache_key, specialties, 3600)
        
        return Response(specialties)
    
    @extend_schema(
        description="Book an appointment with this doctor",
        request=AppointmentBookingSerializer,
        responses={201: AppointmentSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def book_appointment(self, request, pk=None):
        """Book an appointment with this doctor."""
        doctor = self.get_object()
        
        serializer = AppointmentBookingSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            appointment = serializer.save(doctor=doctor)
            response_serializer = AppointmentSerializer(appointment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(description="List appointments"),
    retrieve=extend_schema(description="Get appointment details"),
    create=extend_schema(description="Create a new appointment"),
    update=extend_schema(description="Update appointment"),
    partial_update=extend_schema(description="Partially update appointment"),
    destroy=extend_schema(description="Cancel appointment"),
)
class AppointmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing appointments.
    """
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'doctor', 'appointment_date']
    ordering_fields = ['appointment_date', 'appointment_time', 'created_at']
    ordering = ['appointment_date', 'appointment_time']
    
    def get_queryset(self):
        """Filter appointments based on user role."""
        # Handle swagger fake view
        if getattr(self, 'swagger_fake_view', False):
            return Appointment.objects.none()
        
        user = self.request.user
        
        if user.is_staff:
            return Appointment.objects.select_related('doctor', 'patient')
        
        # Check if user is a doctor
        try:
            doctor = user.doctor_profile
            # Doctor can see their own appointments
            return Appointment.objects.select_related('doctor', 'patient').filter(doctor=doctor)
        except Doctor.DoesNotExist:
            # Regular user can see their own appointments as patient
            return Appointment.objects.select_related('doctor', 'patient').filter(patient=user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ['update', 'partial_update']:
            return AppointmentUpdateSerializer
        return AppointmentSerializer
    
    def perform_create(self, serializer):
        """Set the patient to the current user when creating an appointment."""
        serializer.save(patient=self.request.user)
    
    def perform_update(self, serializer):
        """Ensure proper permissions for updating appointments."""
        appointment = self.get_object()
        user = self.request.user
        
        # Check if user is the patient, doctor, or admin
        if (appointment.patient != user and 
            getattr(user, 'doctor_profile', None) != appointment.doctor and 
            not user.is_staff):
            raise permissions.PermissionDenied(
                "You can only update your own appointments."
            )
        
        serializer.save()
    
    @extend_schema(
        description="Get user's upcoming appointments",
        responses={200: AppointmentSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming appointments for the current user."""
        now = timezone.now()
        queryset = self.get_queryset().filter(
            appointment_date__gte=now.date(),
            status__in=['scheduled', 'confirmed']
        ).select_related('doctor', 'patient').order_by('appointment_date', 'appointment_time')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get user's appointment history",
        responses={200: AppointmentSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get appointment history for the current user."""
        queryset = self.get_queryset().filter(
            status__in=['completed', 'cancelled']
        ).select_related('doctor', 'patient').order_by('-appointment_date', '-appointment_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(description="List doctor availabilities"),
    retrieve=extend_schema(description="Get availability details"),
    create=extend_schema(description="Create availability slot"),
    update=extend_schema(description="Update availability"),
    destroy=extend_schema(description="Delete availability slot"),
)
class DoctorAvailabilityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing doctor availability.
    """
    serializer_class = DoctorAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter availability based on user permissions."""
        user = self.request.user
        
        # For list/retrieve actions, allow anonymous access
        if self.action in ['list', 'retrieve']:
            return DoctorAvailability.objects.select_related('doctor').filter(is_active=True)
        
        # For create/update/delete, user must be authenticated (handled by permissions)
        if user.is_staff:
            return DoctorAvailability.objects.select_related('doctor')
        
        # Check if user is a doctor
        try:
            doctor = user.doctor_profile
            return DoctorAvailability.objects.select_related('doctor').filter(doctor=doctor)
        except Doctor.DoesNotExist:
            # Regular authenticated users can view all availability
            return DoctorAvailability.objects.select_related('doctor').filter(is_active=True)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            # Anyone can view availability
            permission_classes = [permissions.AllowAny]
        else:
            # Only doctors can create/update/delete their availability
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Set the doctor to the current user when creating availability."""
        try:
            doctor = self.request.user.doctor_profile
            serializer.save(doctor=doctor)
        except Doctor.DoesNotExist:
            raise PermissionDenied("Only doctors can create availability slots.")


@extend_schema_view(
    list=extend_schema(description="List doctor reviews"),
    retrieve=extend_schema(description="Get review details"),
    create=extend_schema(description="Create a review for a doctor"),
    update=extend_schema(description="Update your review"),
    destroy=extend_schema(description="Delete your review"),
)
class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing doctor reviews.
    """
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['doctor', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter reviews based on query parameters."""
        queryset = Review.objects.select_related('doctor', 'patient', 'appointment')
        
        # Filter by doctor if specified
        doctor_id = self.request.query_params.get('doctor_id', None)
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        
        return queryset
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            # Anyone can view reviews
            permission_classes = [permissions.AllowAny]
        else:
            # Must be authenticated to create/update/delete reviews
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def perform_update(self, serializer):
        """Ensure only the review author can update."""
        review = self.get_object()
        if review.patient != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You can only update your own reviews.")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Ensure only the review author or admin can delete."""
        if instance.patient != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You can only delete your own reviews.")
        
        instance.delete()
