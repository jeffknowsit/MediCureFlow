"""
Django signals for users app.

This module contains signal handlers for automatic user profile creation,
email notifications, and other automated tasks.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile when a new User is created.
    """
    if created:
        try:
            # Use get_or_create to avoid duplicates
            profile, created_now = UserProfile.objects.get_or_create(user=instance)
            if created_now:
                logger.info(f'User profile created for user: {instance.username}')
        except Exception as e:
            logger.error(f'Error creating user profile for {instance.username}: {e}')
    else:
        # Only create profile if it doesn't exist - don't auto-save existing profiles
        # to avoid race conditions with profile updates
        try:
            if not hasattr(instance, 'profile') or not UserProfile.objects.filter(user=instance).exists():
                UserProfile.objects.create(user=instance)
                logger.info(f'User profile created for user: {instance.username}')
        except Exception as e:
            logger.error(f'Error creating missing profile for {instance.username}: {e}')


@receiver(post_save, sender=UserProfile)
def log_profile_update(sender, instance, created, **kwargs):
    """
    Log profile updates for monitoring.
    """
    action = "created" if created else "updated"
    logger.info(f'User profile {action} for user: {instance.user.username}')


def send_welcome_email(user):
    """
    Send welcome email to new users.
    """
    if not user.email:
        return
    
    try:
        subject = 'Welcome to MediCureFlow!'
        message = f'''
        Dear {user.get_full_name() or user.username},
        
        Welcome to MediCureFlow! Your account has been successfully created.
        
        You can now:
        - Search for doctors by specialty and location
        - Book appointments online
        - Manage your medical profile
        - Track your appointment history
        
        Get started by visiting our website and searching for doctors in your area.
        
        Best regards,
        The MediCureFlow Team
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f'Welcome email sent to: {user.email}')
        
    except Exception as e:
        logger.error(f'Error sending welcome email to {user.email}: {e}')


@receiver(post_save, sender=User)
def send_welcome_email_signal(sender, instance, created, **kwargs):
    """
    Send welcome email when new user is created.
    """
    if created and instance.email:
        send_welcome_email(instance)
