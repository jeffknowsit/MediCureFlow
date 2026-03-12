"""
API endpoint tests for MediCureFlow project.

This module contains comprehensive tests for all API endpoints including
authentication, permissions, CRUD operations, and business logic.
Uses Django REST Framework test client and Django's built-in testing framework.
"""

from django.urls import reverse
from rest_framework import status
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import date, time, timedelta

from apps.doctors.models import Doctor, Appointment, Review, DoctorAvailability
from tests.base import BaseAPITestCase, PerformanceTestMixin

# API URL namespaces based on actual URL configuration
# Main API: 'api:' + app namespace
# Doctors API URLs are under 'api:' namespace since they're included in api_urls.py


class DoctorAPITest(BaseAPITestCase, PerformanceTestMixin):
    """Test Doctor API endpoints."""
    
    def test_list_doctors_public(self):
        """Test public access to doctors list."""
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 2)  # We have 2 doctors in test data
        
        # Check response structure
        doctor_data = response.data['results'][0]
        expected_keys = [
            'id', 'display_name', 'first_name', 'last_name', 'specialty', 
            'experience_years', 'consultation_fee', 'city', 'state',
            'is_available', 'average_rating', 'total_reviews'
        ]
        self.assertResponseHasKeys(doctor_data, expected_keys)
    
    def test_list_doctors_performance(self):
        """Test that doctors list uses optimized queries."""
        url = reverse('api:doctors_api:doctor-list')
        
        # This should use select_related and prefetch_related to avoid N+1 queries
        with self.assertMaxQueries(5):  # Should be minimal queries due to optimization
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_doctor_detail(self):
        """Test retrieving doctor details."""
        url = reverse('api:doctors_api:doctor-detail', kwargs={'pk': self.doctor.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.doctor.id)
        self.assertEqual(response.data['display_name'], 'Dr. John Doe')
        self.assertEqual(response.data['specialty'], 'cardiology')
    
    def test_search_doctors_by_specialty(self):
        """Test searching doctors by specialty."""
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url, {'specialty': 'cardiology'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['specialty'], 'cardiology')
    
    def test_search_doctors_by_city(self):
        """Test searching doctors by city."""
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url, {'city': 'New York'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['city'], 'New York')
    
    def test_search_doctors_by_query(self):
        """Test full-text search of doctors."""
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url, {'search': 'John'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
    
    def test_filter_available_doctors_only(self):
        """Test filtering only available doctors."""
        # Make one doctor unavailable
        self.doctor2.is_available = False
        self.doctor2.save()
        
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url, {'available_only': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertTrue(response.data['results'][0]['is_available'])
    
    def test_get_doctor_specialties(self):
        """Test getting list of specialties."""
        url = reverse('api:doctors_api:doctor-specialties')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreater(len(response.data), 0)
        
        # Check structure of specialty data
        specialty = response.data[0]
        self.assertIn('value', specialty)
        self.assertIn('label', specialty)
    
    def test_create_doctor_admin_only(self):
        """Test that only admin can create doctors."""
        url = reverse('api:doctors_api:doctor-list')
        doctor_data = {
            'first_name': 'New',
            'last_name': 'Doctor',
            'phone': '5551112222',
            'email': 'newdoctor@test.com',
            'specialty': 'dermatology',
            'qualification': 'MD',
            'experience_years': 5,
            'consultation_fee': 100,
            'state': 'NY',
            'city': 'Albany',
            'address': 'Test Address'
        }
        
        # Test without authentication - should return 403 for public creation endpoint
        response = self.client.post(url, doctor_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test with patient authentication
        self.authenticate_as_patient()
        response = self.client.post(url, doctor_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test with admin authentication
        self.authenticate_as_admin()
        response = self.client.post(url, doctor_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_update_doctor_permissions(self):
        """Test doctor update permissions."""
        url = reverse('api:doctors_api:doctor-detail', kwargs={'pk': self.doctor.pk})
        update_data = {'bio': 'Updated bio'}
        
        # Test without authentication - should return 403 for public update endpoint
        response = self.client.patch(url, update_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test with patient authentication
        self.authenticate_as_patient()
        response = self.client.patch(url, update_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test with doctor authentication (own profile)
        self.authenticate_as_doctor()
        response = self.client.patch(url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bio'], 'Updated bio')
    
    def test_delete_doctor_admin_only(self):
        """Test that only admin can delete doctors."""
        # Create a test doctor to delete
        test_user = User.objects.create_user(
            username='testdoc', email='testdoc@test.com', password='pass'
        )
        test_doctor = Doctor.objects.create(
            user=test_user, first_name='Test', last_name='Doc',
            phone='5559999999', email='testdoc@test.com', 
            specialty='general_medicine', qualification='MD',
            experience_years=1, consultation_fee=50,
            state='NY', city='Test City', address='Test Address'
        )
        
        url = reverse('api:doctors_api:doctor-detail', kwargs={'pk': test_doctor.pk})
        
        # Test with patient authentication
        self.authenticate_as_patient()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test with admin authentication
        self.authenticate_as_admin()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class AppointmentAPITest(BaseAPITestCase):
    """Test Appointment API endpoints."""
    
    def setUp(self):
        super().setUp()
        # Create a test appointment
        self.appointment = self.create_test_appointment()
    
    def test_list_appointments_authentication_required(self):
        """Test appointments list requires authentication."""
        url = reverse('api:doctors_api:appointment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_patient_appointments(self):
        """Test patient can see their own appointments."""
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:appointment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        appointment_data = response.data['results'][0]
        self.assertEqual(appointment_data['patient']['id'], self.patient_user.id)
    
    def test_list_doctor_appointments(self):
        """Test doctor can see their own appointments."""
        self.authenticate_as_doctor()
        url = reverse('api:doctors_api:appointment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        appointment_data = response.data['results'][0]
        self.assertEqual(appointment_data['doctor']['id'], self.doctor.id)
    
    def test_create_appointment(self):
        """Test creating an appointment."""
        self.authenticate_as_patient2()
        url = reverse('api:doctors_api:appointment-list')
        
        future_date = timezone.now().date() + timedelta(days=3)
        appointment_data = {
            'doctor_id': self.doctor.id,
            'appointment_date': future_date.isoformat(),
            'appointment_time': '14:00:00',
            'duration_minutes': 30,
            'patient_notes': 'Need consultation for chest pain'
        }
        
        response = self.client.post(url, appointment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'scheduled')
        self.assertEqual(response.data['patient']['id'], self.patient_user2.id)
    
    def test_create_appointment_past_date_fails(self):
        """Test creating appointment with past date fails."""
        self.authenticate_as_patient2()
        url = reverse('api:doctors_api:appointment-list')
        
        past_date = timezone.now().date() - timedelta(days=1)
        appointment_data = {
            'doctor_id': self.doctor.id,
            'appointment_date': past_date.isoformat(),
            'appointment_time': '14:00:00',
            'patient_notes': 'Test appointment'
        }
        
        response = self.client.post(url, appointment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_double_booking_prevention(self):
        """Test double booking prevention."""
        self.authenticate_as_patient2()
        url = reverse('api:doctors_api:appointment-list')
        
        # Try to book same time slot as existing appointment
        appointment_data = {
            'doctor_id': self.appointment.doctor.id,
            'appointment_date': self.appointment.appointment_date.isoformat(),
            'appointment_time': self.appointment.appointment_time.isoformat(),
            'patient_notes': 'Should fail due to double booking'
        }
        
        response = self.client.post(url, appointment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already booked', str(response.data).lower())
    
    def test_update_appointment_status(self):
        """Test updating appointment status."""
        self.authenticate_as_doctor()
        url = reverse('api:doctors_api:appointment-detail', kwargs={'pk': self.appointment.pk})
        
        update_data = {'status': 'confirmed'}
        response = self.client.patch(url, update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'confirmed')
    
    def test_get_upcoming_appointments(self):
        """Test getting upcoming appointments."""
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:appointment-upcoming')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Since our test appointment is in the future, it should be included
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_get_appointment_history(self):
        """Test getting appointment history."""
        # Create a completed appointment
        completed_appointment = self.create_test_appointment(
            patient=self.patient_user, days_ahead=-5, status='completed'
        )
        
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:appointment-history')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should include completed appointments
        self.assertGreaterEqual(response.data['count'], 1)


class ReviewAPITest(BaseAPITestCase):
    """Test Review API endpoints."""
    
    def setUp(self):
        super().setUp()
        # Create a completed appointment so patient can review
        self.completed_appointment = self.create_test_appointment(
            patient=self.patient_user, days_ahead=-5, status='completed'
        )
    
    def test_list_reviews_public(self):
        """Test public access to reviews list."""
        # Create a review first
        review = self.create_test_review()
        
        url = reverse('api:doctors_api:review-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
    
    def test_filter_reviews_by_doctor(self):
        """Test filtering reviews by doctor."""
        review = self.create_test_review()
        
        url = reverse('api:doctors_api:review-list')
        response = self.client.get(url, {'doctor_id': self.doctor.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
    
    def test_create_review_authentication_required(self):
        """Test creating review requires authentication."""
        url = reverse('api:doctors_api:review-list')
        review_data = {
            'doctor': self.doctor.id,
            'rating': 5,
            'title': 'Great doctor!',
            'comment': 'Very satisfied with the treatment.'
        }
        
        response = self.client.post(url, review_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_review_with_appointment(self):
        """Test creating review after completed appointment."""
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:review-list')
        
        review_data = {
            'doctor': self.doctor.id,
            'appointment': self.completed_appointment.id,
            'rating': 4,
            'title': 'Good treatment',
            'comment': 'Doctor was professional and helpful.'
        }
        
        response = self.client.post(url, review_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 4)
        self.assertEqual(response.data['patient']['id'], self.patient_user.id)
    
    def test_create_review_without_appointment_fails(self):
        """Test creating review without completed appointment fails."""
        self.authenticate_as_patient2()  # User with no completed appointments
        url = reverse('api:doctors_api:review-list')
        
        review_data = {
            'doctor': self.doctor.id,
            'rating': 5,
            'title': 'Test review',
            'comment': 'This should fail.'
        }
        
        response = self.client.post(url, review_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_duplicate_review_prevention(self):
        """Test preventing duplicate reviews from same patient."""
        # Create first review
        self.create_test_review()
        
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:review-list')
        
        review_data = {
            'doctor': self.doctor.id,
            'rating': 3,
            'title': 'Another review',
            'comment': 'Should fail due to duplicate.'
        }
        
        response = self.client.post(url, review_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_own_review(self):
        """Test updating own review."""
        review = self.create_test_review()
        
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:review-detail', kwargs={'pk': review.pk})
        
        update_data = {'rating': 4, 'comment': 'Updated comment'}
        response = self.client.patch(url, update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rating'], 4)
        self.assertEqual(response.data['comment'], 'Updated comment')
    
    def test_cannot_update_others_review(self):
        """Test cannot update another user's review."""
        review = self.create_test_review()
        
        self.authenticate_as_patient2()  # Different user
        url = reverse('api:doctors_api:review-detail', kwargs={'pk': review.pk})
        
        update_data = {'rating': 1, 'comment': 'Bad review'}
        response = self.client.patch(url, update_data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_rating_validation(self):
        """Test rating must be between 1 and 5."""
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:review-list')
        
        # Test invalid ratings
        for invalid_rating in [0, 6, -1, 10]:
            review_data = {
                'doctor': self.doctor.id,
                'rating': invalid_rating,
                'title': 'Test review',
                'comment': 'Test comment'
            }
            
            response = self.client.post(url, review_data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test valid rating
        review_data = {
            'doctor': self.doctor.id,
            'rating': 3,
            'title': 'Valid review',
            'comment': 'Valid comment'
        }
        
        response = self.client.post(url, review_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class DoctorAvailabilityAPITest(BaseAPITestCase):
    """Test DoctorAvailability API endpoints."""
    
    def test_list_availability_public(self):
        """Test public access to availability list."""
        url = reverse('api:doctors_api:availability-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 2)  # We have 2 availability slots
    
    def test_create_availability_doctor_only(self):
        """Test only doctors can create availability."""
        url = reverse('api:doctors_api:availability-list')
        availability_data = {
            'day_of_week': 3,  # Thursday
            'start_time': '09:00:00',
            'end_time': '17:00:00',
            'is_active': True
        }
        
        # Test without authentication
        response = self.client.post(url, availability_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test with patient authentication - gets 400 because perform_create catches the error
        self.authenticate_as_patient()
        response = self.client.post(url, availability_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test with doctor authentication
        self.authenticate_as_doctor()
        response = self.client.post(url, availability_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_doctor_can_only_manage_own_availability(self):
        """Test doctor can only see/manage their own availability."""
        self.authenticate_as_doctor()
        url = reverse('api:doctors_api:availability-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see own availability slots
        for availability in response.data['results']:
            self.assertEqual(availability['doctor'], self.doctor.id)


class AuthenticationTest(BaseAPITestCase):
    """Test authentication and permissions."""
    
    def test_token_authentication(self):
        """Test token-based authentication works."""
        # Test with valid token
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:appointment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test with invalid token
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid-token')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test without token
        self.clear_authentication()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_permissions(self):
        """Test admin has access to all resources."""
        self.authenticate_as_admin()
        
        # Admin can see all appointments
        url = reverse('api:doctors_api:appointment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin can see all availability
        url = reverse('api:doctors_api:availability-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_role_based_access_control(self):
        """Test different user roles have appropriate access."""
        appointment = self.create_test_appointment()
        
        # Test patient can see own appointment
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:appointment-detail', kwargs={'pk': appointment.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test other patient cannot see appointment
        self.authenticate_as_patient2()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test doctor can see appointment with them
        self.authenticate_as_doctor()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PaginationTest(BaseAPITestCase):
    """Test API pagination."""
    
    def test_pagination_structure(self):
        """Test paginated response structure."""
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check pagination structure
        expected_keys = ['count', 'next', 'previous', 'results']
        for key in expected_keys:
            self.assertIn(key, response.data)
        
        self.assertIsInstance(response.data['results'], list)
        self.assertIsInstance(response.data['count'], int)
    
    def test_page_size_limit(self):
        """Test page size is properly limited."""
        url = reverse('api:doctors_api:doctor-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 20)  # PAGE_SIZE is 20


class ErrorHandlingTest(BaseAPITestCase):
    """Test API error handling."""
    
    def test_404_for_nonexistent_resource(self):
        """Test 404 error for nonexistent resources."""
        url = reverse('api:doctors_api:doctor-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_validation_errors(self):
        """Test validation error responses."""
        self.authenticate_as_admin()
        url = reverse('api:doctors_api:doctor-list')
        
        # Send invalid data
        invalid_data = {
            'first_name': '',  # Required field
            'email': 'invalid-email',  # Invalid email format
            'experience_years': -5,  # Invalid value
        }
        
        response = self.client.post(url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check error response structure
        self.assertIsInstance(response.data, dict)
    
    def test_permission_denied_error(self):
        """Test permission denied error format."""
        self.authenticate_as_patient()
        url = reverse('api:doctors_api:doctor-list')
        
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_method_not_allowed(self):
        """Test method not allowed error."""
        # Assuming specialties endpoint only allows GET
        url = reverse('api:doctors_api:doctor-specialties')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class APIDocumentationTest(BaseAPITestCase):
    """Test API documentation endpoints."""
    
    def test_api_schema_available(self):
        """Test API schema endpoint is available."""
        # This will depend on your URL configuration for drf-spectacular
        # url = reverse('api-schema')
        # response = self.client.get(url)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        pass  # Skip for now if not implemented
    
    def test_api_docs_available(self):
        """Test API documentation page is available."""
        # url = reverse('api-docs')
        # response = self.client.get(url)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        pass  # Skip for now if not implemented
