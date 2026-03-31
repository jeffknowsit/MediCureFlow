from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.doctors.models import Doctor
import random

class Command(BaseCommand):
    help = 'Seeds the database with dummy doctors for all specialties'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        SPECIALTIES = [s[0] for s in Doctor._meta.get_field('specialty').choices]
        
        FIRST_NAMES = ['John', 'Sarah', 'Michael', 'Emily', 'David', 'Jessica', 'James', 'Ashley', 'Robert', 'Amanda', 'Oliver', 'Charlotte', 'William', 'Amelia', 'Benjamin']
        LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Patel', 'Chen', 'Kim', 'Nguyen', 'Ali']
        
        created_count = 0
        self.stdout.write("Starting to create doctors...")

        for specialty in SPECIALTIES:
            for _ in range(1): # 1 doctor per specialty is enough for testing
                first_name = random.choice(FIRST_NAMES)
                last_name = random.choice(LAST_NAMES)
                
                username = f"dr_{first_name.lower()}_{last_name.lower()}_{random.randint(100, 999)}"
                email = f"{username}@medicureflow.com"
                
                if User.objects.filter(username=username).exists():
                    continue
                    
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='12345678',
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Make them staff so they can use django admin or login to doc panel if needed
                user.is_staff = True
                user.save()
                
                phone = f"+1555{random.randint(1000000, 9999999)}"
                while Doctor.objects.filter(phone=phone).exists():
                    phone = f"+1555{random.randint(1000000, 9999999)}"

                fees = [50.00, 75.00, 100.00, 120.00, 150.00]
                doc = Doctor.objects.create(
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email,
                    specialty=specialty,
                    qualification="MD, Board Certified",
                    experience_years=random.randint(2, 35),
                    consultation_fee=random.choice(fees),
                    state="New York",
                    city="New York",
                    address=f"{random.randint(100, 999)} Medical Ave, Suite {random.randint(1, 99)}",
                    bio=f"Dr. {last_name} is a highly experienced specialist in {specialty}.",
                    is_available=True
                )
                
                created_count += 1
                self.stdout.write(f"Doctor Name: {first_name} {last_name} | Specialty: {doc.get_specialty_display()} | Username/UserID: {username} | Password: 12345678")

        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} random doctors.'))
