"""
Serializers for the users app API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile
# from MediCureFlow.middleware.security import InputSanitizationMixin


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""
    
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'alternate_phone', 'date_of_birth', 'gender', 'address_line1',
            'address_line2', 'city', 'state', 'country', 'postal_code', 'blood_group',
            'allergies', 'chronic_conditions', 'medications', 'emergency_contact_name',
            'emergency_contact_phone', 'emergency_contact_relation', 'profile_picture',
            'email_notifications', 'sms_notifications', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_profile_picture(self, value):
        """Validate profile picture upload."""
        is_valid, error_message = self.validate_file_upload(value)
        if not is_valid:
            raise serializers.ValidationError(error_message)
        return value
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Sanitize text fields
        text_fields = ['address_line1', 'address_line2', 'city', 'state', 'country', 
                      'allergies', 'chronic_conditions', 'medications', 
                      'emergency_contact_name', 'emergency_contact_relation']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = self.sanitize_html_input(data[field])
        
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with profile data."""
    
    profile = UserProfileSerializer(read_only=True)
    password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'profile', 'password'
        ]
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Sanitize text fields
        text_fields = ['first_name', 'last_name', 'username']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = self.sanitize_html_input(data[field])
        
        return super().to_internal_value(data)
    
    def create(self, validated_data):
        """Create a new user with hashed password."""
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """Update user instance."""
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile information."""
    
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'alternate_phone', 'date_of_birth', 'gender', 'address_line1',
            'address_line2', 'city', 'state', 'country', 'postal_code', 'blood_group',
            'allergies', 'chronic_conditions', 'medications', 'emergency_contact_name',
            'emergency_contact_phone', 'emergency_contact_relation', 'profile_picture',
            'email_notifications', 'sms_notifications'
        ]
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if value and len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits.")
        return value
    
    def validate_profile_picture(self, value):
        """Validate profile picture upload."""
        is_valid, error_message = self.validate_file_upload(value)
        if not is_valid:
            raise serializers.ValidationError(error_message)
        return value
    
    def to_internal_value(self, data):
        """Sanitize text inputs."""
        # Sanitize text fields
        text_fields = ['address_line1', 'address_line2', 'city', 'state', 'country', 
                      'allergies', 'chronic_conditions', 'medications', 
                      'emergency_contact_name', 'emergency_contact_relation']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = self.sanitize_html_input(data[field])
        
        return super().to_internal_value(data)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    # Optional profile fields during registration
    phone = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=UserProfile.GENDER_CHOICES,
        required=False,
        allow_blank=True
    )
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'phone', 'date_of_birth',
            'gender', 'city', 'state'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True}
        }
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return attrs
    
    def validate_email(self, value):
        """Check if email is already registered."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    
    def create(self, validated_data):
        """Create user with profile information."""
        # Remove password_confirm and profile fields
        validated_data.pop('password_confirm')
        profile_data = {
            'phone': validated_data.pop('phone', ''),
            'date_of_birth': validated_data.pop('date_of_birth', None),
            'gender': validated_data.pop('gender', ''),
            'city': validated_data.pop('city', ''),
            'state': validated_data.pop('state', ''),
        }
        
        # Create user
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create or update user profile with additional data
        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        for field, value in profile_data.items():
            if value:  # Only set non-empty values
                setattr(profile, field, value)
        profile.save()
        
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validate password change data."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords do not match.")
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class UserPublicSerializer(serializers.ModelSerializer):
    """Serializer for public user information (used in appointments, etc.)."""
    
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']
