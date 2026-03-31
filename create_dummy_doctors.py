import os
import django
import random

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MediCureFlow.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.doctors.models import Doctor

User = get_user_model()

# List of all available specialties from the model
SPECIALTIES = [s[0] for s in Doctor._meta.get_field('specialty').choices]

# List of realistic dummy names
FIRST_NAMES = ['John', 'Sarah', 'Michael', 'Emily', 'David', 'Jessica', 'James', 'Ashley', 'Robert', 'Amanda', 'Oliver', 'Charlotte', 'William', 'Amelia', 'Benjamin', 'Mia']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Patel', 'Chen', 'Kim', 'Nguyen', 'Ali']

created_count = 0

for specialty in SPECIALTIES:
    # Let's create 2 doctors per specialty
    for _ in range(2):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        
        # Ensure unique username
        username = f"dr_{first_name.lower()}_{last_name.lower()}_{random.randint(1000, 9999)}"
        email = f"{username}@medicureflow.com"
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            continue
            
        print(f"Creating doctor: {first_name} {last_name} ({specialty}) - Username: {username}")
        
        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password='12345678',
            first_name=first_name,
            last_name=last_name
        )
        # Give them staff access so they can login to the doctor panel if needed
        # Or at least set them up as active
        
        # Generate random unique phone
        phone = f"+1{random.randint(200,999)}{random.randint(200,999)}{random.randint(1000,9999)}"
        while Doctor.objects.filter(phone=phone).exists():
            phone = f"+1{random.randint(200,999)}{random.randint(200,999)}{random.randint(1000,9999)}"

        # Create Doctor Profile
        fees = [50.00, 75.00, 100.00, 120.00, 150.00, 200.00]
        Doctor.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            specialty=specialty,
            license_number=f"MD{random.randint(100000, 999999)}",
            experience_years=random.randint(2, 35),
            consultation_fee=random.choice(fees),
            about=f"Dr. {last_name} is a highly experienced specialist in {specialty}.",
            is_available=True
        )
        created_count += 1

print(f"\nSuccessfully created {created_count} random doctors across all specialties.")
