"""
Forms for doctors app.

This module contains form classes for doctor registration, appointments,
availability management, and other doctor-related functionality.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Doctor, Appointment, DoctorAvailability, Review
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, HTML, Field
from crispy_forms.bootstrap import FormActions
from decimal import Decimal


class DoctorRegistrationForm(UserCreationForm):
    """
    Registration form for doctors with professional information.
    """
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Professional Email'})
    )
    phone = forms.CharField(
        max_length=17,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Phone Number'})
    )
    
    # Professional fields
    specialty = forms.ChoiceField(
        choices=Doctor.SPECIALTIES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    qualification = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Medical Qualifications (e.g., MBBS, MD)'})
    )
    experience_years = forms.IntegerField(
        required=True,
        min_value=0,
        max_value=60,
        widget=forms.NumberInput(attrs={'placeholder': 'Years of Experience'})
    )
    consultation_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'placeholder': 'Consultation Fee (₹)'})
    )
    
    # Location fields
    state = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'State'})
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'City'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Complete Address'})
    )
    
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Brief professional biography (optional)'})
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h2 class=\"text-center mb-4\">Doctor Registration</h2>'),
            
            HTML('<h4>Personal Information</h4>'),
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
            'phone',
            Row(
                Column('password1', css_class='form-group col-md-6'),
                Column('password2', css_class='form-group col-md-6'),
                css_class='row'
            ),
            
            HTML('<h4 class=\"mt-4\">Professional Information</h4>'),
            Row(
                Column('specialty', css_class='form-group col-md-6'),
                Column('experience_years', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'qualification',
            'consultation_fee',
            
            HTML('<h4 class=\"mt-4\">Practice Location</h4>'),
            Row(
                Column('state', css_class='form-group col-md-6'),
                Column('city', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'address',
            'bio',
            
            FormActions(
                Submit('submit', 'Register as Doctor', css_class='btn btn-success btn-lg w-100')
            )
        )
        
        # Update placeholders
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
            # Create doctor profile
            Doctor.objects.create(
                user=user,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                email=self.cleaned_data['email'],
                phone=self.cleaned_data['phone'],
                specialty=self.cleaned_data['specialty'],
                qualification=self.cleaned_data['qualification'],
                experience_years=self.cleaned_data['experience_years'],
                consultation_fee=self.cleaned_data['consultation_fee'],
                state=self.cleaned_data['state'],
                city=self.cleaned_data['city'],
                address=self.cleaned_data['address'],
                bio=self.cleaned_data.get('bio', ''),
            )
        return user


class DoctorProfileForm(forms.ModelForm):
    """
    Form for updating doctor profile information.
    """
    
    class Meta:
        model = Doctor
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'specialty',
            'qualification', 'experience_years', 'consultation_fee',
            'state', 'city', 'address', 'photo', 'bio', 'is_available',
            'is_on_duty', 'lunch_break_start', 'lunch_break_end'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'lunch_break_start': forms.TimeInput(attrs={'type': 'time'}),
            'lunch_break_end': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Personal Information</h3>'),
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
                css_class='row'
            ),
            Row(
                Column('email', css_class='form-group col-md-6'),
                Column('phone', css_class='form-group col-md-6'),
                css_class='row'
            ),
            
            HTML('<h3 class=\"mt-4\">Professional Information</h3>'),
            Row(
                Column('specialty', css_class='form-group col-md-6'),
                Column('experience_years', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'qualification',
            Row(
                Column('consultation_fee', css_class='form-group col-md-4'),
                Column('is_available', css_class='form-group col-md-4'),
                Column('is_on_duty', css_class='form-group col-md-4'),
                css_class='row'
            ),
            
            HTML('<h3 class="mt-4">Lunch Break Settings</h3>'),
            Row(
                Column('lunch_break_start', css_class='form-group col-md-6'),
                Column('lunch_break_end', css_class='form-group col-md-6'),
                css_class='row'
            ),
            
            HTML('<h3 class=\"mt-4\">Location</h3>'),
            Row(
                Column('state', css_class='form-group col-md-6'),
                Column('city', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'address',
            
            HTML('<h3 class=\"mt-4\">Profile</h3>'),
            'photo',
            'bio',
            
            FormActions(
                Submit('submit', 'Update Profile', css_class='btn btn-primary btn-lg')
            )
        )


class AppointmentForm(forms.ModelForm):
    """
    Form for booking appointments.
    """
    
    class Meta:
        model = Appointment
        fields = [
            'appointment_date', 'appointment_time', 'duration_minutes', 'patient_notes'
        ]
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
            'patient_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['duration_minutes'].required = False
        self.fields['duration_minutes'].initial = 30
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Book Appointment</h3>'),
            Row(
                Column('appointment_date', css_class='form-group col-md-6'),
                Column('appointment_time', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'duration_minutes',
            'patient_notes',
            FormActions(
                Submit('submit', 'Book Appointment', css_class='btn btn-success btn-lg')
            )
        )


class DoctorAvailabilityForm(forms.ModelForm):
    """
    Form for managing doctor availability.
    """
    
    class Meta:
        model = DoctorAvailability
        fields = ['day_of_week', 'start_time', 'end_time', 'is_active']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Set Availability</h3>'),
            'day_of_week',
            Row(
                Column('start_time', css_class='form-group col-md-6'),
                Column('end_time', css_class='form-group col-md-6'),
                css_class='row'
            ),
            'is_active',
            FormActions(
                Submit('submit', 'Save Availability', css_class='btn btn-primary')
            )
        )


class ReviewForm(forms.ModelForm):
    """
    Form for submitting doctor reviews.
    """
    
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Write a Review</h3>'),
            'rating',
            'title',
            'comment',
            FormActions(
                Submit('submit', 'Submit Review', css_class='btn btn-success')
            )
        )


class AppointmentUpdateForm(forms.ModelForm):
    """
    Form for updating appointment status and notes (for doctors).
    """
    
    class Meta:
        model = Appointment
        fields = ['status', 'doctor_notes', 'is_paid']
        widgets = {
            'doctor_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h3>Update Appointment</h3>'),
            'status',
            'is_paid',
            'doctor_notes',
            FormActions(
                Submit('submit', 'Update Appointment', css_class='btn btn-primary')
            )
        )
