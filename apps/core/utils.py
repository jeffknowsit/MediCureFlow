"""
Common utility functions for MediCureFlow project.

This module contains shared utility functions to reduce code duplication
across different apps.
"""

import json
import logging
from django.contrib import messages
from django.urls import reverse_lazy
from django.conf import settings

logger = logging.getLogger(__name__)


class FormMessageMixin:
    """
    Mixin to provide standard form success/error messages.
    """
    success_message = None
    error_message = None

    def form_valid(self, form):
        """Handle successful form submission with standard message."""
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response

    def form_invalid(self, form):
        """Handle failed form submission with standard message."""
        if self.error_message:
            messages.error(self.request, self.error_message)
        return super().form_invalid(form)


class AuthenticationMessageMixin:
    """
    Mixin to provide standard authentication messages.
    """
    def form_invalid(self, form):
        """Handle failed authentication with standard message."""
        messages.error(self.request, 'Invalid username or password.')
        return super().form_invalid(form)


def serialize_chart_data(data):
    """
    Convert chart data to JSON for JavaScript consumption.
    
    Args:
        data (dict): Chart data dictionary
        
    Returns:
        str: JSON string representation of the data
    """
    try:
        return json.dumps(data)
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing chart data: {e}")
        return json.dumps({})


def get_currency_context():
    """
    Get currency information for templates.
    
    Returns:
        dict: Currency context with symbol and code
    """
    currency = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
    currency_symbols = getattr(settings, 'CURRENCY_SYMBOLS', {
        'USD': '$',
        'INR': '₹',
        'EUR': '€',
        'GBP': '£'
    })
    return {
        'current_currency': currency,
        'currency_symbol': currency_symbols.get(currency, '$'),
    }


def get_user_dashboard_redirect(user):
    """
    Get appropriate dashboard URL based on user type.
    
    Args:
        user: Django User instance
        
    Returns:
        str: URL name for appropriate dashboard
    """
    if hasattr(user, 'doctor_profile'):
        return reverse_lazy('doctors:dashboard')
    elif user.is_staff:
        return reverse_lazy('admin_system:dashboard')
    else:
        return reverse_lazy('users:dashboard')


def log_user_action(user, action, details=None):
    """
    Log user actions for audit trail.
    
    Args:
        user: Django User instance
        action (str): Description of the action
        details (str, optional): Additional details
    """
    log_message = f"User {user.username} performed action: {action}"
    if details:
        log_message += f" - {details}"
    logger.info(log_message)


def safe_divide(numerator, denominator, default=0):
    """
    Safely divide two numbers, returning default if division by zero.
    
    Args:
        numerator (float): The numerator
        denominator (float): The denominator
        default (float): Default value if denominator is zero
        
    Returns:
        float: Result of division or default value
    """
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ValueError):
        return default


def format_phone_number(phone):
    """
    Format phone number for display.
    
    Args:
        phone (str): Raw phone number
        
    Returns:
        str: Formatted phone number or original if formatting fails
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Format based on length
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Return original if can't format


def mask_phone_number(phone_number=None, unique_id=None):
    """
    Return a masked phone number for privacy protection.
    
    This function returns a masked phone number in the format +91 XXXX-XXX-XXX
    to prevent accidental calls to real numbers in demo/development environments.
    
    Args:
        phone_number: Any phone number (will be ignored for masking)
        unique_id: Optional unique identifier to make phone number unique
        
    Returns:
        str: Masked phone number in format "+91 XXXX-XXX-XXX" or unique variant
    """
    if unique_id:
        return f"+91 XXXX-XXX-{unique_id:03d}"
    return "+91 XXXX-XXX-XXX"


def get_demo_phone_number():
    """
    Get a demo phone number for testing purposes.
    
    Returns:
        str: A clearly fake phone number that won't cause accidental calls
    """
    return "+91 XXXX-XXX-XXX"


def is_demo_environment():
    """
    Check if the current environment is demo/development.
    
    Returns:
        bool: True if in demo environment, False otherwise
    """
    return getattr(settings, 'DEBUG', False) or getattr(settings, 'DEMO_MODE', True)
