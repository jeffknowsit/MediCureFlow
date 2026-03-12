"""
Base test utilities and fixtures for MediCureFlow project.

This module provides common test utilities, fixtures, and base classes
for consistent testing across the application.
Uses only Django's built-in testing framework.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from apps.doctors.models import Doctor, Appointment, Review, DoctorAvailability
from apps.users.models import UserProfile
from datetime import date, time, timedelta
import tempfile
from PIL import Image


class BaseTestCase(TestCase):
    """Base test case with common fixtures and utilities."""
    
    @classmethod
    def setUpTestData(cls):
        """Create common test data used across multiple tests."""
        # Create test users
        cls.admin_user = User.objects.create_user(
            username='admin',
            email='admin@MediCureFlow.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=True
        )
        
        cls.doctor_user = User.objects.create_user(
            username='drdoe',
            email='doctor@MediCureFlow.com',
            password='doctorpass123',
            first_name='John',
            last_name='Doe'
        )
        
        cls.patient_user = User.objects.create_user(
            username='patient',
            email='patient@MediCureFlow.com',
            password='patientpass123',
            first_name='Jane',
            last_name='Smith'
        )
        
        cls.patient_user2 = User.objects.create_user(
            username='patient2',
            email='patient2@MediCureFlow.com',
            password='patientpass123',
            first_name='Bob',
            last_name='Johnson'
        )
        
        # Update user profiles (they're created automatically by signals)
        cls.patient_profile = cls.patient_user.profile
        cls.patient_profile.date_of_birth = date(1990, 5, 15)
        cls.patient_profile.gender = 'F'
        cls.patient_profile.phone = '1234567890'
        cls.patient_profile.city = 'New York'
        cls.patient_profile.state = 'NY'
        cls.patient_profile.blood_group = 'A+'
        cls.patient_profile.save()
        
        cls.patient_profile2 = cls.patient_user2.profile
        cls.patient_profile2.date_of_birth = date(1985, 3, 20)
        cls.patient_profile2.gender = 'M'
        cls.patient_profile2.phone = '9876543210'
        cls.patient_profile2.city = 'Los Angeles'
        cls.patient_profile2.state = 'CA'
        cls.patient_profile2.blood_group = 'O+'
        cls.patient_profile2.save()
        
        # Create doctor profile
        cls.doctor = Doctor.objects.create(
            user=cls.doctor_user,
            first_name='John',
            last_name='Doe',
            phone='5551234567',
            email='doctor@MediCureFlow.com',
            specialty='cardiology',
            qualification='MD, Cardiology',
            experience_years=10,
            consultation_fee=150.00,
            state='NY',
            city='New York',
            address='123 Medical Center Drive',
            bio='Experienced cardiologist with 10 years of practice.',
            is_available=True
        )
        
        # Create another doctor for testing
        cls.doctor2_user = User.objects.create_user(
            username='drsmith',
            email='smith@MediCureFlow.com',
            password='doctorpass123',
            first_name='Sarah',
            last_name='Smith'
        )
        
        cls.doctor2 = Doctor.objects.create(
            user=cls.doctor2_user,
            first_name='Sarah',
            last_name='Smith',
            phone='5559876543',
            email='smith@MediCureFlow.com',
            specialty='pediatrics',
            qualification='MD, Pediatrics',
            experience_years=8,
            consultation_fee=120.00,
            state='CA',
            city='Los Angeles',
            address='456 Children Hospital Lane',
            bio='Pediatric specialist focused on child healthcare.',
            is_available=True
        )
        
        # Create doctor availability
        cls.availability = DoctorAvailability.objects.create(
            doctor=cls.doctor,
            day_of_week=1,  # Tuesday
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True
        )
        
        cls.availability2 = DoctorAvailability.objects.create(
            doctor=cls.doctor,
            day_of_week=2,  # Wednesday
            start_time=time(10, 0),
            end_time=time(16, 0),
            is_active=True
        )

    def create_test_appointment(self, doctor=None, patient=None, days_ahead=1, 
                              status='scheduled', appointment_time=None):
        """Create a test appointment with sensible defaults."""
        if doctor is None:
            doctor = self.doctor
        if patient is None:
            patient = self.patient_user
        if appointment_time is None:
            appointment_time = time(10, 0)
            
        appointment_date = timezone.now().date() + timedelta(days=days_ahead)
        
        return Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status=status,
            patient_notes='Test appointment notes',
            fee_charged=doctor.consultation_fee
        )
    
    def create_test_review(self, doctor=None, patient=None, rating=5, 
                          title='Great doctor!'):
        """Create a test review with sensible defaults."""
        if doctor is None:
            doctor = self.doctor
        if patient is None:
            patient = self.patient_user
            
        return Review.objects.create(
            doctor=doctor,
            patient=patient,
            rating=rating,
            title=title,
            comment='Test review comment. Very satisfied with the treatment.'
        )
    
    def create_test_image(self):
        """Create a temporary test image for file upload tests."""
        image = Image.new('RGB', (100, 100), 'red')
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        image.save(temp_file, 'JPEG')
        temp_file.flush()
        return temp_file


class BaseAPITestCase(APITestCase, BaseTestCase):
    """Base API test case with authentication utilities."""
    
    def setUp(self):
        """Set up API client and authentication."""
        super().setUp()
        self.client = APIClient()
        
        # Create tokens for users
        self.admin_token = Token.objects.create(user=self.admin_user)
        self.doctor_token = Token.objects.create(user=self.doctor_user)
        self.patient_token = Token.objects.create(user=self.patient_user)
        self.patient_token2 = Token.objects.create(user=self.patient_user2)
    
    def authenticate_as_admin(self):
        """Authenticate API client as admin user."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
    
    def authenticate_as_doctor(self):
        """Authenticate API client as doctor user."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.doctor_token.key}')
    
    def authenticate_as_patient(self):
        """Authenticate API client as patient user."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.patient_token.key}')
    
    def authenticate_as_patient2(self):
        """Authenticate API client as second patient user."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.patient_token2.key}')
    
    def clear_authentication(self):
        """Clear authentication credentials."""
        self.client.credentials()
    
    def assertResponseHasKeys(self, response_data, expected_keys):
        """Assert that response data contains expected keys."""
        if isinstance(response_data, list) and response_data:
            # Check first item in list
            response_data = response_data[0]
        
        for key in expected_keys:
            self.assertIn(key, response_data, f"Key '{key}' not found in response")
    
    def assertValidationError(self, response, field=None, status_code=400):
        """Assert that response contains validation error."""
        self.assertEqual(response.status_code, status_code)
        if field:
            self.assertIn(field, response.data)


class ModelTestMixin:
    """Mixin for testing Django model functionality."""
    
    def assertModelFieldExists(self, model_class, field_name):
        """Assert that a model field exists."""
        self.assertTrue(
            hasattr(model_class, field_name),
            f"Field '{field_name}' does not exist in {model_class.__name__}"
        )
    
    def assertModelMethodExists(self, model_instance, method_name):
        """Assert that a model method exists and is callable."""
        self.assertTrue(
            hasattr(model_instance, method_name),
            f"Method '{method_name}' does not exist"
        )
        self.assertTrue(
            callable(getattr(model_instance, method_name)),
            f"'{method_name}' is not callable"
        )
    
    def assertValidModel(self, model_instance):
        """Assert that a model instance is valid."""
        try:
            model_instance.full_clean()
        except Exception as e:
            self.fail(f"Model validation failed: {e}")


class PerformanceTestMixin:
    """Mixin for testing performance and query optimization."""
    
    def assertMaxQueries(self, max_queries):
        """Context manager to assert maximum number of queries."""
        from django.test.utils import override_settings
        from django.db import connection
        
        class QueryCounter:
            def __init__(self, max_queries):
                self.max_queries = max_queries
                self.initial_queries = 0
            
            def __enter__(self):
                self.initial_queries = len(connection.queries)
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                executed_queries = len(connection.queries) - self.initial_queries
                if executed_queries > self.max_queries:
                    query_list = connection.queries[self.initial_queries:]
                    queries_str = '\n'.join([q['sql'] for q in query_list])
                    self.fail(
                        f"Expected maximum {self.max_queries} queries, "
                        f"but {executed_queries} were executed:\n{queries_str}"
                    )
        
        return QueryCounter(max_queries)


# Test data constants
TEST_SPECIALTIES = [
    'cardiology', 'neurosurgery', 'pediatrics', 'dermatology', 
    'orthopedics', 'general_medicine'
]

TEST_STATES = ['NY', 'CA', 'TX', 'FL', 'IL']
TEST_CITIES = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix']

# Utility functions for test data creation
def create_test_user(username, email, is_staff=False, is_superuser=False):
    """Create a test user with default values."""
    return User.objects.create_user(
        username=username,
        email=email,
        password='testpass123',
        first_name='Test',
        last_name='User',
        is_staff=is_staff,
        is_superuser=is_superuser
    )
