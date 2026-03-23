"""
Forms for users app.

This module contains form classes for user registration, authentication,
profile management, and other user-related functionality.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, HTML, Div, Field
from crispy_forms.bootstrap import FormActions
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import UploadedFile

def process_profile_picture(image_file):
    """Compress and resize profile picture for SQLite blob storage."""
    if not image_file or not isinstance(image_file, UploadedFile):
        return None, None
    try:
        img = Image.open(image_file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize to max 300x300 while maintaining aspect ratio
        img.thumbnail((300, 300))
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=70)
        return output.getvalue(), 'image/jpeg'
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error compressing image: {e}")
        return None, None


class CustomUserRegistrationForm(UserCreationForm):
    """
    Extended user registration form with additional fields.
    """
    first_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email Address'})
    )
    phone = forms.CharField(
        max_length=17, 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Phone Number (Optional)'})
    )
    profile_picture = forms.ImageField(
        required=False,
        help_text='Upload a profile picture (optional)',
        widget=forms.FileInput(attrs={'class': 'custom-file-input', 'accept': 'image/*'})
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h2 class="text-center mb-4">Create Your Account</h2>'),
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
                css_class='row'
            ),
            Row(
                Column('username', css_class='form-group col-md-6'),
                Column('email', css_class='form-group col-md-6'),
                css_class='row'
            ),
            Row(
                Column('phone', css_class='form-group col-md-6'),
                Column('profile_picture', css_class='form-group col-md-6'),
                css_class='row'
            ),
            Row(
                Column('password1', css_class='form-group col-md-6'),
                Column('password2', css_class='form-group col-md-6'),
                css_class='row'
            ),
            FormActions(
                Submit('submit', 'Create Account', css_class='btn btn-primary btn-lg w-100')
            )
        )
        
        # Update field placeholders and help text
        self.fields['username'].widget.attrs.update({'placeholder': 'Username'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm Password'})

    def clean_email(self):
        """
        Validate that the email address is unique.
        """
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'A user with this email address already exists. Please use a different email.'
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create user profile
            profile = UserProfile.objects.create(
                user=user,
                phone=self.cleaned_data.get('phone', ''),
                profile_picture=self.cleaned_data.get('profile_picture') or 'users/profiles/default.png'
            )
            
            pic = self.cleaned_data.get('profile_picture')
            if pic:
                blob, mime = process_profile_picture(pic)
                if blob:
                    profile.profile_picture_blob = blob
                    profile.profile_picture_mime = mime
                    profile.save(update_fields=['profile_picture_blob', 'profile_picture_mime'])
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that supports login with username or email.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Update the username field to be more descriptive
        self.fields['username'].label = 'Username or Email'
        self.fields['username'].help_text = 'You can use either your username or email address'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h2 class="text-center mb-4">Sign In</h2>'),
            Field('username', placeholder='Username or Email'),
            Field('password', placeholder='Password'),
            FormActions(
                Submit('submit', 'Sign In', css_class='btn btn-primary btn-lg w-100'),
                HTML('<div class="text-center mt-3">'),
                HTML('<a href="{% url \'register\' %}" class="text-decoration-none">Don\'t have an account? Register here</a>'),
                HTML('</div>')
            )
        )
        
        # Update field widgets
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username or Email',
            'autocomplete': 'username email'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'current-password'
        })


class UserProfileForm(forms.ModelForm):
    """
    Form for updating user profile information.
    """
    
    class Meta:
        model = UserProfile
        fields = [
            'date_of_birth', 'gender', 'phone', 'alternate_phone',
            'address_line1', 'address_line2', 'city', 'state', 
            'postal_code', 'country', 'blood_group', 'allergies', 
            'chronic_conditions', 'medications', 'emergency_contact_name',
            'emergency_contact_phone', 'emergency_contact_relation',
            'profile_picture', 'email_notifications', 'sms_notifications'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'allergies': forms.Textarea(attrs={'rows': 3}),
            'chronic_conditions': forms.Textarea(attrs={'rows': 3}),
            'medications': forms.Textarea(attrs={'rows': 3}),
            'profile_picture': forms.FileInput(attrs={'class': 'custom-file-input', 'accept': 'image/*'}),
        }

    def save(self, commit=True):
        profile = super().save(commit=False)
        pic = self.cleaned_data.get('profile_picture')
        
        if pic:
            blob, mime = process_profile_picture(pic)
            if blob:
                profile.profile_picture_blob = blob
                profile.profile_picture_mime = mime
                
        if commit:
            profile.save()
        return profile

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Personal Information</h3>'),
            Row(
                Column('date_of_birth', css_class='form-group col-md-6'),
                Column('gender', css_class='form-group col-md-6'),
                css_class='row'
            ),
            Row(
                Column('phone', css_class='form-group col-md-6'),
                Column('alternate_phone', css_class='form-group col-md-6'),
                css_class='row'
            ),
            
            HTML('<h3 class="mt-4">Address Information</h3>'),
            'address_line1',
            'address_line2',
            Row(
                Column('city', css_class='form-group col-md-4'),
                Column('state', css_class='form-group col-md-4'),
                Column('postal_code', css_class='form-group col-md-4'),
                css_class='row'
            ),
            'country',
            
            HTML('<h3 class="mt-4">Medical Information</h3>'),
            Row(
                Column('blood_group', css_class='form-group col-md-6'),
                Column('profile_picture', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'allergies',
            'chronic_conditions',
            'medications',
            
            HTML('<h3 class="mt-4">Emergency Contact</h3>'),
            Row(
                Column('emergency_contact_name', css_class='form-group col-md-6'),
                Column('emergency_contact_relation', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'emergency_contact_phone',
            
            HTML('<h3 class="mt-4">Preferences</h3>'),
            Row(
                Column('email_notifications', css_class='form-group col-md-6'),
                Column('sms_notifications', css_class='form-group col-md-6'),
                css_class='row'
            ),
            
            FormActions(
                Submit('submit', 'Update Profile', css_class='btn btn-primary btn-lg')
            )
        )


class UserUpdateForm(forms.ModelForm):
    """
    Form for updating basic user information.
    """
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Basic Information</h3>'),
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'email',
            FormActions(
                Submit('submit', 'Update Information', css_class='btn btn-primary')
            )
        )


class DoctorSearchForm(forms.Form):
    """
    Advanced form for searching doctors with comprehensive filtering.
    """
    
    from apps.doctors.models import Doctor
    
    SORT_CHOICES = [
        ('relevance', 'Best Match'),
        ('rating', 'Highest Rated'), 
        ('experience', 'Most Experienced'),
        ('reviews', 'Most Reviewed'),
        ('fee_low', 'Lowest Fee'),
        ('fee_high', 'Highest Fee'),
        ('newest', 'Newest'),
        ('name', 'Name A-Z'),
    ]
    
    RATING_CHOICES = [
        ('', 'Any Rating'),
        ('4.0', '4+ Stars'),
        ('4.5', '4.5+ Stars'),
        ('5.0', '5 Stars Only'),
    ]
    
    EXPERIENCE_CHOICES = [
        ('', 'Any Experience'),
        ('1', '1+ Years'),
        ('3', '3+ Years'),
        ('5', '5+ Years'),
        ('10', '10+ Years'),
        ('15', '15+ Years'),
    ]
    
    LANGUAGE_CHOICES = [
        ('', 'Any Language'),
        ('English', 'English'),
        ('Hindi', 'Hindi'),
        ('Bengali', 'Bengali'),
        ('Tamil', 'Tamil'),
        ('Telugu', 'Telugu'),
        ('Marathi', 'Marathi'),
        ('Gujarati', 'Gujarati'),
    ]
    
    # Basic search
    search_query = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, specialty, qualification...'
        })
    )
    
    # Location filters
    city = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter city...'
        })
    )
    
    state = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter state...'
        })
    )
    
    # Specialty filter
    specialty = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Experience filter
    min_experience = forms.ChoiceField(
        required=False,
        choices=EXPERIENCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Fee filter
    max_fee = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Maximum fee...',
            'step': '100'
        })
    )
    
    # Rating filter
    rating_min = forms.ChoiceField(
        required=False,
        choices=RATING_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Language filter
    language = forms.ChoiceField(
        required=False,
        choices=LANGUAGE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Verification filter
    verified_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Show only verified doctors'
    )
    
    # Sort options
    sort_by = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        initial='relevance',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Import here to avoid circular import
        from apps.doctors.models import Doctor
        
        # Set specialty choices from model
        self.fields['specialty'].choices = [('', 'All Specialties')] + list(Doctor.SPECIALTIES)
        
        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.form_id = 'doctor-search-form'
        self.helper.layout = Layout(
            # Basic search row
            Row(
                Column('search_query', css_class='col-md-6'),
                Column('sort_by', css_class='col-md-3'),
                Column(
                    HTML('<button type="submit" class="btn btn-primary w-100 mt-4"><i class="bi bi-search me-2"></i>Search</button>'),
                    css_class='col-md-3'
                ),
                css_class='mb-4'
            ),
            
            # Advanced filters in collapsible section
            HTML('<div class="card mb-4">'),
            HTML('<div class="card-header">'),
            HTML('<h6 class="mb-0">'),
            HTML('<button class="btn btn-link collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#advanced-filters">'),
            HTML('<i class="bi bi-funnel me-2"></i>Advanced Filters'),
            HTML('</button>'),
            HTML('</h6>'),
            HTML('</div>'),
            HTML('<div id="advanced-filters" class="collapse">'),
            HTML('<div class="card-body">'),
            
            # Location filters
            HTML('<h6>Location</h6>'),
            Row(
                Column('city', css_class='col-md-6'),
                Column('state', css_class='col-md-6'),
                css_class='mb-3'
            ),
            
            # Professional filters
            HTML('<h6>Professional Details</h6>'),
            Row(
                Column('specialty', css_class='col-md-4'),
                Column('min_experience', css_class='col-md-4'),
                Column('language', css_class='col-md-4'),
                css_class='mb-3'
            ),
            
            # Rating and fee filters
            HTML('<h6>Rating & Fees</h6>'),
            Row(
                Column('rating_min', css_class='col-md-6'),
                Column('max_fee', css_class='col-md-6'),
                css_class='mb-3'
            ),
            
            # Verification filter
            HTML('<div class="form-check">'),
            Field('verified_only'),
            HTML('</div>'),
            
            HTML('</div>'),
            HTML('</div>'),
            HTML('</div>')
        )
