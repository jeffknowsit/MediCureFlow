from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.urls import reverse
from PIL import Image


class UserProfile(models.Model):
    """
    Extended user profile model for patients.
    
    This model stores additional information about users/patients
    including contact details, preferences, and medical history.
    """
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('P', 'Prefer not to say'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    
    # Core relationship
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Personal Information
    full_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full name of the user"
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Date of birth"
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        help_text="Gender"
    )
    
    # Contact Information
    phone_regex = RegexValidator(
        regex=r'^[\+\(]?[0-9][\d\s\-\(\)]*$',
        message="Phone number can contain digits, spaces, dashes, parentheses, and + sign. Examples: +91 9876543210, (555) 123-4567, 555-123-4567"
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=20,
        blank=True,
        help_text="Primary contact phone number (e.g., +91 9876543210, (555) 123-4567)"
    )
    alternate_phone = models.CharField(
        validators=[phone_regex],
        max_length=20,
        blank=True,
        help_text="Alternate contact phone number (e.g., +91 9876543210, (555) 123-4567)"
    )
    
    # Address Information
    address_line1 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Address line 1"
    )
    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Address line 2 (optional)"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City"
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="State/Province"
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal/ZIP code"
    )
    country = models.CharField(
        max_length=100,
        default='India',
        help_text="Country"
    )
    
    # Medical Information
    blood_group = models.CharField(
        max_length=3,
        choices=BLOOD_GROUP_CHOICES,
        blank=True,
        help_text="Blood group"
    )
    allergies = models.TextField(
        blank=True,
        help_text="Known allergies (separate with commas)"
    )
    chronic_conditions = models.TextField(
        blank=True,
        help_text="Chronic medical conditions"
    )
    medications = models.TextField(
        blank=True,
        help_text="Current medications"
    )
    
    # Emergency Contact
    emergency_contact_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Emergency contact person name"
    )
    emergency_contact_phone = models.CharField(
        validators=[phone_regex],
        max_length=20,
        blank=True,
        help_text="Emergency contact phone number (e.g., +91 9876543210, (555) 123-4567)"
    )
    emergency_contact_relation = models.CharField(
        max_length=100,
        blank=True,
        help_text="Relationship with emergency contact"
    )
    
    # Profile Picture
    profile_picture = models.ImageField(
        upload_to='users/profiles/%Y/%m/',
        default='users/profiles/default.png',
        help_text="Legacy Profile picture field"
    )
    profile_picture_blob = models.BinaryField(
        null=True,
        blank=True,
        help_text="Profile picture stored in SQLite"
    )
    profile_picture_mime = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Mime type of the SQLite profile picture"
    )
    
    # Preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications"
    )
    sms_notifications = models.BooleanField(
        default=True,
        help_text="Receive SMS notifications"
    )
    
    # Additional profile information
    occupation = models.CharField(
        max_length=200,
        blank=True,
        help_text="Current occupation"
    )
    insurance_provider = models.CharField(
        max_length=200,
        blank=True,
        help_text="Health insurance provider"
    )
    insurance_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Health insurance policy number"
    )
    
    # Activity tracking
    last_appointment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date of last appointment"
    )
    total_appointments = models.PositiveIntegerField(
        default=0,
        help_text="Total number of appointments booked"
    )
    
    # Verification status
    is_phone_verified = models.BooleanField(
        default=False,
        help_text="Whether phone number is verified"
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Whether email is verified"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}'s Profile"
    
    @property
    def full_address(self):
        """Return formatted full address."""
        address_parts = []
        if self.address_line1:
            address_parts.append(self.address_line1)
        if self.address_line2:
            address_parts.append(self.address_line2)
        if self.city:
            address_parts.append(self.city)
        if self.state:
            address_parts.append(self.state)
        if self.postal_code:
            address_parts.append(self.postal_code)
        # Only include country if it's not the default 'India' OR if we have a complete address
        if self.country and self.country != 'India':
            address_parts.append(self.country)
        elif self.country == 'India' and self.address_line1 and self.postal_code:
            # Include India only if we have a street address and postal code
            address_parts.append(self.country)
        return ', '.join(address_parts)
    
    @property
    def has_profile_picture(self):
        """Return True if the user has a profile picture (either blob or file)."""
        return bool(self.profile_picture_blob or self.profile_picture)

    @property
    def age(self):
        """Calculate age from date of birth."""
        if not self.date_of_birth:
            return None
        
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    @property
    def profile_picture_url(self):
        """Return the profile picture URL using the SQLite binary storage with fallback to ImageField."""
        if self.profile_picture_blob:
            return reverse('users:profile_image', kwargs={'user_id': self.user.id})
        
        if self.profile_picture:
            try:
                return self.profile_picture.url
            except ValueError:
                pass
        
        # Fallback to the default image if no blob or file is found
        from django.templatetags.static import static
        return static('images/default-user.png')
    
    def get_absolute_url(self):
        """Return the absolute URL for this profile."""
        return reverse('users:profile', kwargs={'pk': self.pk})
    
    def update_appointment_stats(self):
        """Update user's appointment statistics."""
        from apps.doctors.models import Appointment
        
        # Get latest appointment
        latest_appointment = Appointment.objects.filter(
            patient=self.user
        ).order_by('-appointment_date', '-appointment_time').first()
        
        if latest_appointment:
            self.last_appointment_date = latest_appointment.appointment_datetime
        
        # Update total appointments count
        self.total_appointments = Appointment.objects.filter(
            patient=self.user
        ).count()
        
        self.save(update_fields=['last_appointment_date', 'total_appointments'])
    
    def save(self, *args, **kwargs):
        """Override save."""
        super().save(*args, **kwargs)
