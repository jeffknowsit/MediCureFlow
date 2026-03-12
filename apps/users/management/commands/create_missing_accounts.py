from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.doctors.models import Doctor
from apps.users.models import UserProfile


class Command(BaseCommand):
    help = 'Create missing user accounts for doctors and patients'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Creating missing accounts and updating credentials...\n")
        
        # Check doctors without user accounts
        doctors_without_users = Doctor.objects.filter(user__isnull=True)
        doctors_with_users = Doctor.objects.filter(user__isnull=False)
        
        self.stdout.write(f"Doctors with user accounts: {doctors_with_users.count()}")
        self.stdout.write(f"Doctors without user accounts: {doctors_without_users.count()}")
        
        # Check patients/users without profiles
        users_without_profiles = User.objects.filter(userprofile__isnull=True, is_superuser=False, is_staff=False)
        users_with_profiles = User.objects.filter(userprofile__isnull=False)
        
        self.stdout.write(f"Users with profiles: {users_with_profiles.count()}")
        self.stdout.write(f"Users without profiles: {users_without_profiles.count()}")
        
        # Create missing doctor accounts
        doctor_credentials = []
        for i, doctor in enumerate(doctors_without_users):
            username = f"dr.{doctor.full_name.lower().split()[0]}"
            # Handle duplicates
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            email = f"{username}@MediCureFlow.com"
            password = f"Doctor@{1000 + i}"
            
            # Create user account
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=doctor.full_name.split()[0],
                last_name=' '.join(doctor.full_name.split()[1:]) if len(doctor.full_name.split()) > 1 else ''
            )
            
            # Link to doctor profile
            doctor.user = user
            doctor.save()
            
            doctor_credentials.append({
                'username': username,
                'email': email,
                'password': password,
                'name': doctor.full_name,
                'specialty': doctor.specialization,
                'experience': f"{doctor.experience_years} years",
                'fee': f"₹{doctor.consultation_fee}",
                'location': doctor.city
            })
            
            self.stdout.write(f"✓ Created account for Dr. {doctor.full_name} ({username})")
        
        # Create missing patient profiles for existing users
        patient_credentials = []
        for i, user in enumerate(users_without_profiles):
            if not user.is_superuser and not user.is_staff:
                # Create user profile
                profile = UserProfile.objects.create(
                    user=user,
                    full_name=f"{user.first_name} {user.last_name}".strip() or f"Patient {user.username}",
                    phone=f"+91{9000000000 + i}",
                    date_of_birth="1990-01-01",
                    gender="other",
                    emergency_contact_name="Emergency Contact",
                    emergency_contact_phone=f"+91{8000000000 + i}"
                )
                
                patient_credentials.append({
                    'username': user.username,
                    'email': user.email,
                    'password': "Password varies - check credentials file",
                    'name': profile.full_name
                })
                
                self.stdout.write(f"✓ Created profile for {profile.full_name} ({user.username})")
        
        # Generate additional patient accounts
        sample_patients = [
            "Abhishek Kumar", "Akash Sharma", "Ananya Patel", "Arjun Singh", "Divya Gupta",
            "Kavya Reddy", "Manish Agarwal", "Neha Malhotra", "Priya Joshi", "Rahul Mehta",
            "Sakshi Verma", "Shreya Das", "Tanvi Kapoor", "Utkarsh Nair", "Vidya Rao"
        ]
        
        new_patient_creds = []
        for i, name in enumerate(sample_patients):
            first_name = name.split()[0].lower()
            username = f"{first_name}.patient{i+10}"
            
            # Check if username exists
            if User.objects.filter(username=username).exists():
                continue
                
            email = f"{first_name.lower()}.{name.split()[1].lower()}@example.com"
            password = f"Patient@{500 + i}"
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=name.split()[0],
                last_name=name.split()[1] if len(name.split()) > 1 else ''
            )
            
            # Create profile
            profile = UserProfile.objects.create(
                user=user,
                full_name=name,
                phone=f"+91{9100000000 + i}",
                date_of_birth="1992-01-01",
                gender="other",
                emergency_contact_name=f"{name} Emergency",
                emergency_contact_phone=f"+91{8100000000 + i}"
            )
            
            new_patient_creds.append({
                'username': username,
                'email': email,
                'password': password,
                'name': name
            })
            
            self.stdout.write(f"✓ Created new patient account: {name} ({username})")
        
        # Update credentials file
        self.update_credentials_file()
        
        self.stdout.write("\n🎉 Account creation and credentials update completed!")
        self.stdout.write("\nSummary:")
        self.stdout.write(f"- New doctor accounts: {len(doctor_credentials)}")
        self.stdout.write(f"- New patient profiles: {len(patient_credentials)}")
        self.stdout.write(f"- New patient accounts: {len(new_patient_creds)}")
        self.stdout.write("\n📄 Check sample_data/CREDENTIALS_AND_TESTING_GUIDE.md for all login details")

    def update_credentials_file(self):
        """Update the credentials file with all accounts"""
        
        # Get all current accounts
        all_doctors = Doctor.objects.filter(user__isnull=False).select_related('user').order_by('full_name')
        all_patients = UserProfile.objects.all().select_related('user').order_by('full_name')
        
        credentials_content = """# MediCureFlow - Complete Credentials and Testing Guide

## 🔐 User Credentials for Testing

### 👨‍💼 Administrator Account
- **Username:** `admin`
- **Email:** `admin@MediCureFlow.com`
- **Password:** `Admin@2025`
- **Role:** Super Admin
- **Access:** Full system access, admin dashboard, user/doctor management

### 👥 Patient/User Accounts

"""
        
        # Add patient credentials
        for i, patient in enumerate(all_patients, 1):
            password = self.get_patient_password(patient.user.username)
            credentials_content += f"""#### Patient {i} - {patient.full_name}
- **Username:** `{patient.user.username}`
- **Email:** `{patient.user.email}`
- **Password:** `{password}`
- **Profile:** {patient.full_name}

"""
        
        credentials_content += "\n### 👨‍⚕️ Doctor Accounts\n\n"
        
        # Add doctor credentials
        for doctor in all_doctors:
            fee_display = f"₹{doctor.consultation_fee}" if doctor.consultation_fee else "₹1000"
            password = self.get_doctor_password(doctor.user.username)
            credentials_content += f"""#### Dr. {doctor.full_name} - {doctor.specialization}
- **Username:** `{doctor.user.username}`
- **Email:** `{doctor.user.email}`
- **Password:** `{password}`
- **Specialty:** {doctor.specialization}
- **Experience:** {doctor.experience_years} years
- **Fee:** {fee_display}
- **Location:** {doctor.city}

"""
        
        # Add testing scenarios and other content
        credentials_content += """
## 🧪 Testing Scenarios

### 1. Patient Journey Testing
1. **Registration & Login**
   - Register as new patient
   - Login with existing patient credentials
   - Complete profile information

2. **Doctor Search & Discovery**
   - Search by specialty (e.g., cardiology, dermatology)
   - Filter by location, experience, fee range
   - View doctor profiles with ratings and reviews

3. **Appointment Booking**
   - Select doctor and preferred time slot
   - Fill in consultation details and symptoms
   - Confirm booking and receive confirmation

4. **Health Checkup**
   - Access health assessment feature
   - Input symptoms for preliminary analysis
   - Receive personalized health recommendations

5. **Patient Dashboard**
   - View upcoming and past appointments
   - Track health records and medical history
   - Manage profile and preferences

### 2. Doctor Journey Testing
1. **Doctor Login**
   - Login with doctor credentials
   - Access doctor dashboard

2. **Appointment Management**
   - View today's appointments
   - Update appointment status
   - Add consultation notes

3. **Patient Records**
   - Access patient medical history
   - Review symptoms and health data
   - Update treatment recommendations

4. **Profile Management**
   - Update professional information
   - Manage availability schedule
   - Set consultation fees

### 3. Admin Journey Testing
1. **Admin Access**
   - Login with admin credentials
   - Access comprehensive admin dashboard

2. **User Management**
   - View and manage patient accounts
   - Monitor doctor profiles and verification
   - Handle user queries and issues

3. **System Analytics**
   - Review platform usage statistics
   - Monitor appointment trends
   - Analyze revenue and growth metrics

## 🚀 Quick Start Testing Guide

### Step 1: Start the Development Server
```bash
python manage.py runserver
```

### Step 2: Test Basic Functionality
1. **Homepage**: Visit `http://127.0.0.1:8000/`
2. **Patient Login**: Use any patient credentials above
3. **Doctor Login**: Use any doctor credentials above
4. **Admin Access**: Use admin credentials for system management

### Step 3: Test Key Features
1. **Search Doctors**: Search by specialty or location
2. **Book Appointment**: Complete an appointment booking flow
3. **Health Check**: Try the symptom checker
4. **Dashboard**: Explore patient and doctor dashboards
5. **Admin Panel**: Check system analytics and management tools

## 📝 Testing Notes

### Security Notes
- All passwords follow secure patterns with special characters
- Email addresses use realistic domains for testing
- All user data is for testing purposes only

---

**Happy Testing! 🎉**

*MediCureFlow - Making Healthcare Accessible for Everyone*
"""
        
        # Write to file
        with open('sample_data/CREDENTIALS_AND_TESTING_GUIDE.md', 'w', encoding='utf-8') as f:
            f.write(credentials_content)
        
        self.stdout.write("\n✓ Updated CREDENTIALS_AND_TESTING_GUIDE.md")

    def get_doctor_password(self, username):
        """Get password for doctor based on username"""
        password_map = {
            'dr.aadhav': 'Doctor@123',
            'dr.aashna': 'Doctor@456', 
            'dr.amiya': 'Doctor@789',
            'dr.anya': 'Doctor@101',
            'dr.charvi': 'Doctor@202',
            'dr.isha': 'Doctor@303',
            'dr.kabir': 'Doctor@404',
            'dr.kyro': 'Doctor@505',
            'dr.liana': 'Doctor@606',
            'dr.myra': 'Doctor@707',
            'dr.ojas': 'Doctor@808',
            'dr.ronav': 'Doctor@909',
            'dr.vanya': 'Doctor@111',
            'dr.vihaan': 'Doctor@222'
        }
        
        return password_map.get(username, 'Doctor@999')

    def get_patient_password(self, username):
        """Get password for patient based on username"""
        password_map = {
            'aarnav.patient': 'Patient@123',
            'aarohi.patient': 'Patient@456',
            'advik.patient': 'Patient@789',
            'isha.patient': 'Patient@101',
            'ivaan.patient': 'Patient@202',
            'kalp.patient': 'Patient@303',
            'zayn.patient': 'Patient@404'
        }
        
        # For new patients created by script
        if username.startswith(('abhishek', 'akash', 'ananya', 'arjun', 'divya')):
            return username.split('.')[0].title() + '@500'
        elif username.startswith(('kavya', 'manish', 'neha', 'priya', 'rahul')):
            return username.split('.')[0].title() + '@505'
        elif username.startswith(('sakshi', 'shreya', 'tanvi', 'utkarsh', 'vidya')):
            return username.split('.')[0].title() + '@510'
        
        return password_map.get(username, 'Patient@999')
