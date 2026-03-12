"""
Django management command to populate the database with sample data.

This command creates:
- Sample doctors with specialties
- Sample users (patients)
- Sample appointments
- Sample reviews
- User accounts with credentials

Usage: python manage.py populate_sample_data
"""

import os
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.conf import settings

from apps.doctors.models import Doctor, Appointment, DoctorAvailability, Review
from apps.users.models import UserProfile


class Command(BaseCommand):
    help = 'Populate database with sample data for development and testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating',
        )
        parser.add_argument(
            '--doctors-only',
            action='store_true',
            help='Only create doctors, not patients or appointments',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting sample data population...'))
        
        if options['clear']:
            self.clear_existing_data()
        
        # Create sample data
        credentials = []
        
        # Create admin user if not exists
        admin_credentials = self.create_admin_user()
        if admin_credentials:
            credentials.append(admin_credentials)
        
        # Create doctors
        doctor_credentials = self.create_sample_doctors()
        credentials.extend(doctor_credentials)
        
        if not options['doctors_only']:
            # Create patients
            patient_credentials = self.create_sample_patients()
            credentials.extend(patient_credentials)
            
            # Create appointments
            self.create_sample_appointments()
            
            # Create reviews
            self.create_sample_reviews()
        
        # Save credentials to file
        self.save_credentials_file(credentials)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated database with sample data!\n'
                f'Credentials saved to: sample_credentials.txt'
            )
        )
    
    def clear_existing_data(self):
        """Clear existing sample data."""
        self.stdout.write('Clearing existing data...')
        
        # Clear all data except superusers
        Review.objects.all().delete()
        Appointment.objects.all().delete()
        DoctorAvailability.objects.all().delete()
        Doctor.objects.all().delete()
        UserProfile.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS('Existing data cleared.'))
    
    def create_admin_user(self):
        """Create admin user if not exists."""
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@MediCureFlow.com',
                password='admin123',
                first_name='System',
                last_name='Administrator'
            )
            self.stdout.write(f'Created admin user: {admin.username}')
            return {
                'type': 'Admin',
                'username': 'admin',
                'password': 'admin123',
                'email': 'admin@MediCureFlow.com',
                'name': 'System Administrator'
            }
        return None
    
    def create_sample_doctors(self):
        """Create sample doctors with different specialties."""
        doctors_data = [
            {
                'username': 'dr.smith',
                'email': 'john.smith@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'John',
                'last_name': 'Smith',
                'specialty': 'cardiology',
                'qualification': 'MBBS, MD Cardiology',
                'experience_years': 15,
                'consultation_fee': 200.00,
                'phone': '+91 XXXX-XXX-001',
                'address': '123 Heart Care Center',
                'city': 'New York',
                'state': 'NY',
                'bio': 'Experienced cardiologist specializing in heart disease prevention and treatment. Board certified with 15+ years of practice.',
                'photo': 'person_1.jpg'
            },
            {
                'username': 'dr.johnson',
                'email': 'sarah.johnson@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'specialty': 'dermatology',
                'qualification': 'MBBS, MD Dermatology',
                'experience_years': 12,
                'consultation_fee': 180.00,
                'phone': '+91 XXXX-XXX-002',
                'address': '456 Skin Care Clinic',
                'city': 'Los Angeles',
                'state': 'CA',
                'bio': 'Dermatologist with expertise in skin disorders, cosmetic dermatology, and skin cancer screening.',
                'photo': 'person_2.jpg'
            },
            {
                'username': 'dr.williams',
                'email': 'michael.williams@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'Michael',
                'last_name': 'Williams',
                'specialty': 'orthopedics',
                'qualification': 'MBBS, MS Orthopedics',
                'experience_years': 18,
                'consultation_fee': 220.00,
                'phone': '+91 XXXX-XXX-003',
                'address': '789 Bone & Joint Institute',
                'city': 'Chicago',
                'state': 'IL',
                'bio': 'Orthopedic surgeon specializing in joint replacement, sports injuries, and trauma surgery.',
                'photo': 'person_3.jpg'
            },
            {
                'username': 'dr.brown',
                'email': 'lisa.brown@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'Lisa',
                'last_name': 'Brown',
                'specialty': 'pediatrics',
                'qualification': 'MBBS, MD Pediatrics',
                'experience_years': 10,
                'consultation_fee': 160.00,
                'phone': '+91 XXXX-XXX-004',
                'address': '321 Children\'s Medical Center',
                'city': 'Houston',
                'state': 'TX',
                'bio': 'Pediatrician dedicated to providing comprehensive healthcare for infants, children, and adolescents.',
                'photo': 'person_4.jpg'
            },
            {
                'username': 'dr.davis',
                'email': 'robert.davis@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'Robert',
                'last_name': 'Davis',
                'specialty': 'neurology',
                'qualification': 'MBBS, DM Neurology',
                'experience_years': 20,
                'consultation_fee': 250.00,
                'phone': '+91 XXXX-XXX-005',
                'address': '654 Neuro Sciences Center',
                'city': 'Miami',
                'state': 'FL',
                'bio': 'Neurologist with extensive experience in treating neurological disorders, stroke, and epilepsy.',
                'photo': 'unsplash-1.jpg'
            },
            {
                'username': 'dr.wilson',
                'email': 'emma.wilson@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'Emma',
                'last_name': 'Wilson',
                'specialty': 'gynecology',
                'qualification': 'MBBS, MD Obstetrics & Gynecology',
                'experience_years': 14,
                'consultation_fee': 190.00,
                'phone': '+91 XXXX-XXX-006',
                'address': '987 Women\'s Health Center',
                'city': 'Seattle',
                'state': 'WA',
                'bio': 'OB/GYN specialist providing comprehensive women\'s healthcare including pregnancy care and gynecological surgeries.',
                'photo': 'default.png'
            },
            {
                'username': 'dr.anderson',
                'email': 'david.anderson@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'David',
                'last_name': 'Anderson',
                'specialty': 'psychiatry',
                'qualification': 'MBBS, MD Psychiatry',
                'experience_years': 16,
                'consultation_fee': 230.00,
                'phone': '+91 XXXX-XXX-007',
                'address': '147 Mental Health Institute',
                'city': 'Boston',
                'state': 'MA',
                'bio': 'Psychiatrist specializing in anxiety, depression, and behavioral disorders with a focus on holistic treatment approaches.',
                'photo': 'default.png'
            },
            {
                'username': 'dr.taylor',
                'email': 'jennifer.taylor@MediCureFlow.com',
                'password': 'doctor123',
                'first_name': 'Jennifer',
                'last_name': 'Taylor',
                'specialty': 'ophthalmology',
                'qualification': 'MBBS, MS Ophthalmology',
                'experience_years': 11,
                'consultation_fee': 175.00,
                'phone': '+91 XXXX-XXX-008',
                'address': '258 Eye Care Center',
                'city': 'Phoenix',
                'state': 'AZ',
                'bio': 'Ophthalmologist providing comprehensive eye care including cataract surgery, glaucoma treatment, and vision correction.',
                'photo': 'default.png'
            }
        ]
        
        credentials = []
        
        for doctor_data in doctors_data:
            # Create user account
            user_data = {
                'username': doctor_data['username'],
                'email': doctor_data['email'],
                'first_name': doctor_data['first_name'],
                'last_name': doctor_data['last_name'],
            }
            
            if not User.objects.filter(username=doctor_data['username']).exists():
                user = User.objects.create_user(
                    password=doctor_data['password'],
                    **user_data
                )
                
                # Create doctor profile
                doctor = Doctor.objects.create(
                    user=user,
                    first_name=doctor_data['first_name'],
                    last_name=doctor_data['last_name'],
                    specialty=doctor_data['specialty'],
                    qualification=doctor_data['qualification'],
                    experience_years=doctor_data['experience_years'],
                    phone=doctor_data['phone'],
                    email=doctor_data['email'],
                    address=doctor_data['address'],
                    city=doctor_data['city'],
                    state=doctor_data['state'],
                    consultation_fee=doctor_data['consultation_fee'],
                    bio=doctor_data['bio'],
                    is_available=True
                )
                
                # Set doctor photo if available
                photo_path = os.path.join(settings.BASE_DIR, 'media', 'doctors_pics', doctor_data['photo'])
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as photo_file:
                        doctor.photo.save(
                            f"doctor_{doctor.id}_{doctor_data['photo']}",
                            File(photo_file)
                        )
                
                # Create availability (Monday to Friday, 9 AM to 5 PM)
                for day in range(5):  # 0-4 (Monday to Friday)
                    DoctorAvailability.objects.create(
                        doctor=doctor,
                        day_of_week=day,
                        start_time='09:00',
                        end_time='17:00',
                        is_active=True
                    )
                
                self.stdout.write(f'Created doctor: Dr. {doctor.first_name} {doctor.last_name} ({doctor.specialty})')
                
                credentials.append({
                    'type': 'Doctor',
                    'username': doctor_data['username'],
                    'password': doctor_data['password'],
                    'email': doctor_data['email'],
                    'name': f"Dr. {doctor.first_name} {doctor.last_name}",
                    'specialty': doctor.specialty
                })
        
        return credentials
    
    def create_sample_patients(self):
        """Create sample patient accounts."""
        patients_data = [
            {
                'username': 'patient1',
                'email': 'john.doe@email.com',
                'password': 'patient123',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '+91 XXXX-XXX-201',
                'date_of_birth': '1985-03-15',
                'gender': 'M',
                'city': 'New York',
                'state': 'NY'
            },
            {
                'username': 'patient2',
                'email': 'jane.smith@email.com',
                'password': 'patient123',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'phone': '+91 XXXX-XXX-202',
                'date_of_birth': '1990-07-22',
                'gender': 'F',
                'city': 'Los Angeles',
                'state': 'CA'
            },
            {
                'username': 'patient3',
                'email': 'mike.johnson@email.com',
                'password': 'patient123',
                'first_name': 'Mike',
                'last_name': 'Johnson',
                'phone': '+91 XXXX-XXX-203',
                'date_of_birth': '1978-11-08',
                'gender': 'M',
                'city': 'Chicago',
                'state': 'IL'
            },
            {
                'username': 'patient4',
                'email': 'emily.brown@email.com',
                'password': 'patient123',
                'first_name': 'Emily',
                'last_name': 'Brown',
                'phone': '+91 XXXX-XXX-204',
                'date_of_birth': '1992-05-30',
                'gender': 'F',
                'city': 'Houston',
                'state': 'TX'
            },
            {
                'username': 'patient5',
                'email': 'alex.davis@email.com',
                'password': 'patient123',
                'first_name': 'Alex',
                'last_name': 'Davis',
                'phone': '+91 XXXX-XXX-205',
                'date_of_birth': '1988-09-12',
                'gender': 'M',
                'city': 'Miami',
                'state': 'FL'
            }
        ]
        
        credentials = []
        
        for patient_data in patients_data:
            if not User.objects.filter(username=patient_data['username']).exists():
                # Create user account
                user = User.objects.create_user(
                    username=patient_data['username'],
                    email=patient_data['email'],
                    password=patient_data['password'],
                    first_name=patient_data['first_name'],
                    last_name=patient_data['last_name']
                )
                
                # Update user profile (created by signals)
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.phone = patient_data['phone']
                profile.date_of_birth = patient_data['date_of_birth']
                profile.gender = patient_data['gender']
                profile.city = patient_data['city']
                profile.state = patient_data['state']
                profile.save()
                
                self.stdout.write(f'Created patient: {user.first_name} {user.last_name}')
                
                credentials.append({
                    'type': 'Patient',
                    'username': patient_data['username'],
                    'password': patient_data['password'],
                    'email': patient_data['email'],
                    'name': f"{user.first_name} {user.last_name}"
                })
        
        return credentials
    
    def create_sample_appointments(self):
        """Create sample appointments."""
        doctors = Doctor.objects.all()
        patients = User.objects.filter(doctor_profile__isnull=True, is_superuser=False)
        
        if not doctors.exists() or not patients.exists():
            self.stdout.write('No doctors or patients available for appointments')
            return
        
        # Create appointments for the next 30 days
        appointment_count = 0
        
        for i in range(20):  # Create 20 sample appointments
            doctor = random.choice(doctors)
            patient = random.choice(patients)
            
            # Random date in the next 30 days
            days_ahead = random.randint(1, 30)
            appointment_date = timezone.now().date() + timedelta(days=days_ahead)
            
            # Random time during business hours
            hour = random.randint(9, 16)
            minute = random.choice([0, 30])
            appointment_time = f"{hour:02d}:{minute:02d}"
            
            # Random status
            status = random.choice(['scheduled', 'confirmed', 'completed'])
            
            try:
                appointment = Appointment.objects.create(
                    doctor=doctor,
                    patient=patient,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status=status,
                    patient_notes=f"Consultation for {random.choice(['routine checkup', 'follow-up', 'specific concern'])}",
                    fee_charged=doctor.consultation_fee
                )
                appointment_count += 1
            except Exception:
                # Skip if appointment conflicts
                continue
        
        self.stdout.write(f'Created {appointment_count} sample appointments')
    
    def create_sample_reviews(self):
        """Create sample reviews for doctors."""
        doctors = Doctor.objects.all()
        patients = User.objects.filter(doctor_profile__isnull=True, is_superuser=False)
        
        if not doctors.exists() or not patients.exists():
            return
        
        sample_comments = [
            "Excellent doctor! Very professional and thorough.",
            "Great bedside manner and explained everything clearly.",
            "Highly recommend. Very knowledgeable and caring.",
            "Quick and efficient appointment. Good advice given.",
            "Doctor was patient and answered all my questions.",
            "Very satisfied with the consultation and treatment.",
            "Professional service and clean facility.",
            "Doctor took time to listen to my concerns.",
        ]
        
        review_count = 0
        
        for doctor in doctors:
            # Create 2-5 reviews per doctor
            num_reviews = random.randint(2, 5)
            
            for _ in range(num_reviews):
                patient = random.choice(patients)
                
                # Check if this patient already reviewed this doctor
                if not Review.objects.filter(doctor=doctor, patient=patient).exists():
                    Review.objects.create(
                        doctor=doctor,
                        patient=patient,
                        rating=random.randint(3, 5),  # Good to excellent ratings
                        comment=random.choice(sample_comments)
                    )
                    review_count += 1
        
        self.stdout.write(f'Created {review_count} sample reviews')
    
    def save_credentials_file(self, credentials):
        """Save all credentials to a file."""
        credentials_file = os.path.join(settings.BASE_DIR, 'sample_credentials.txt')
        
        with open(credentials_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("MediCureFlowLURE - SAMPLE ACCOUNT CREDENTIALS\n")
            f.write("="*60 + "\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            
            # Group by type
            for account_type in ['Admin', 'Doctor', 'Patient']:
                type_credentials = [c for c in credentials if c['type'] == account_type]
                
                if type_credentials:
                    f.write(f"{account_type.upper()} ACCOUNTS\n")
                    f.write("-" * 30 + "\n")
                    
                    for cred in type_credentials:
                        f.write(f"Name: {cred['name']}\n")
                        f.write(f"Username: {cred['username']}\n")
                        f.write(f"Password: {cred['password']}\n")
                        f.write(f"Email: {cred['email']}\n")
                        if 'specialty' in cred:
                            f.write(f"Specialty: {cred['specialty'].title()}\n")
                        f.write("\n")
                    
                    f.write("\n")
            
            f.write("QUICK ACCESS URLS\n")
            f.write("-" * 20 + "\n")
            f.write("Application: http://127.0.0.1:8000/\n")
            f.write("Admin Panel: http://127.0.0.1:8000/admin/\n")
            f.write("API Docs: http://127.0.0.1:8000/api/docs/\n")
            f.write("Find Doctors: http://127.0.0.1:8000/users/doctors/\n")
            f.write("\n")
            
            f.write("NOTES\n")
            f.write("-" * 10 + "\n")
            f.write("- All doctor accounts have availability Monday-Friday 9AM-5PM\n")
            f.write("- Sample appointments and reviews have been created\n")
            f.write("- Doctor photos are linked to images in media/doctors_pics/\n")
            f.write("- All passwords are for development use only\n")
            f.write("- Change passwords before production deployment\n")
        
        self.stdout.write(f'Credentials saved to: {credentials_file}')
