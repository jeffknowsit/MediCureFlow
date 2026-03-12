from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .services import NotificationService, send_appointment_confirmation, send_welcome_message
import logging

logger = logging.getLogger(__name__)

# Import models after Django is ready to avoid circular imports
try:
    from apps.users.models import Appointment
    from apps.doctors.models import Doctor
    from apps.users.models import UserProfile
except ImportError:
    # Models not yet available (during initial migration)
    Appointment = None
    Doctor = None
    UserProfile = None


@receiver(post_save, sender=User)
def send_welcome_notification(sender, instance, created, **kwargs):
    """Send welcome notification to new users"""
    if created and instance.is_active:
        try:
            # Determine user type
            user_type = 'patient'
            if hasattr(instance, 'doctor'):
                user_type = 'doctor'
            elif instance.is_staff:
                user_type = 'admin'
            
            # Send welcome message
            send_welcome_message(instance, user_type)
            logger.info(f"Welcome notification sent to {instance.username}")
            
        except Exception as e:
            logger.error(f"Error sending welcome notification to {instance.username}: {str(e)}")


if Appointment:
    @receiver(post_save, sender=Appointment)
    def handle_appointment_notifications(sender, instance, created, **kwargs):
        """Handle appointment-related notifications"""
        try:
            service = NotificationService()
            
            if created:
                # New appointment created
                send_appointment_confirmation(instance)
                logger.info(f"Appointment confirmation sent for appointment {instance.id}")
                
                # Notify doctor about new appointment
                service.create_notification(
                    recipient=instance.doctor.user,
                    notification_type='new_appointment',
                    title='New Appointment Request',
                    message=f'You have a new appointment request from {instance.patient.get_full_name()} for {instance.date} at {instance.time}.',
                    priority='high',
                    content_object=instance,
                    extra_data={
                        'appointment_id': instance.id,
                        'patient_name': instance.patient.get_full_name(),
                        'appointment_date': instance.date.isoformat(),
                        'appointment_time': instance.time.isoformat()
                    }
                )
                
            else:
                # Appointment updated
                if instance.status == 'confirmed':
                    # Appointment confirmed by doctor
                    service.create_notification(
                        recipient=instance.patient,
                        notification_type='appointment_confirmed',
                        title='Appointment Confirmed',
                        message=f'Your appointment with Dr. {instance.doctor.user.get_full_name()} has been confirmed for {instance.date} at {instance.time}.',
                        priority='high',
                        content_object=instance
                    )
                    
                elif instance.status == 'cancelled':
                    # Appointment cancelled
                    # Notify both patient and doctor
                    service.create_notification(
                        recipient=instance.patient,
                        notification_type='appointment_cancelled',
                        title='Appointment Cancelled',
                        message=f'Your appointment with Dr. {instance.doctor.user.get_full_name()} on {instance.date} has been cancelled.',
                        priority='high',
                        content_object=instance
                    )
                    
                    service.create_notification(
                        recipient=instance.doctor.user,
                        notification_type='appointment_cancelled',
                        title='Appointment Cancelled',
                        message=f'Your appointment with {instance.patient.get_full_name()} on {instance.date} has been cancelled.',
                        priority='normal',
                        content_object=instance
                    )
                    
                elif instance.status == 'completed':
                    # Appointment completed
                    service.create_notification(
                        recipient=instance.patient,
                        notification_type='appointment_completed',
                        title='Appointment Completed',
                        message=f'Your appointment with Dr. {instance.doctor.user.get_full_name()} has been completed. Please consider leaving a review.',
                        priority='normal',
                        content_object=instance
                    )
                    
        except Exception as e:
            logger.error(f"Error handling appointment notifications for appointment {instance.id}: {str(e)}")


if Doctor:
    @receiver(post_save, sender=Doctor)
    def handle_doctor_notifications(sender, instance, created, **kwargs):
        """Handle doctor-related notifications"""
        try:
            service = NotificationService()
            
            if created:
                # New doctor registered
                service.create_notification(
                    recipient=instance.user,
                    notification_type='doctor_registration',
                    title='Doctor Registration Successful',
                    message='Welcome to MediCure Plus! Your doctor profile has been created successfully. You can now start managing appointments and connecting with patients.',
                    priority='normal',
                    content_object=instance
                )
                
                # Notify admins about new doctor registration
                admin_users = User.objects.filter(is_staff=True, is_active=True)
                for admin in admin_users:
                    service.create_notification(
                        recipient=admin,
                        notification_type='new_doctor_registration',
                        title='New Doctor Registration',
                        message=f'A new doctor {instance.user.get_full_name()} has registered on the platform.',
                        priority='normal',
                        content_object=instance,
                        extra_data={
                            'doctor_name': instance.user.get_full_name(),
                            'doctor_specialty': instance.specialty,
                            'doctor_id': instance.id
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error handling doctor notifications for doctor {instance.id}: {str(e)}")


# Review notifications (assuming Review model exists)
try:
    from apps.doctors.models import Review
    
    @receiver(post_save, sender=Review)
    def handle_review_notifications(sender, instance, created, **kwargs):
        """Handle review-related notifications"""
        if created:
            try:
                service = NotificationService()
                
                # Notify doctor about new review
                service.create_notification(
                    recipient=instance.doctor.user,
                    notification_type='new_review',
                    title='New Patient Review',
                    message=f'You have received a new review from {instance.patient.get_full_name()} with {instance.rating} stars.',
                    priority='normal',
                    content_object=instance,
                    extra_data={
                        'rating': instance.rating,
                        'patient_name': instance.patient.get_full_name(),
                        'review_id': instance.id
                    }
                )
                
                logger.info(f"Review notification sent for review {instance.id}")
                
            except Exception as e:
                logger.error(f"Error handling review notification for review {instance.id}: {str(e)}")
                
except ImportError:
    # Review model not available
    pass


# Profile completion reminders
if UserProfile:
    @receiver(post_save, sender=UserProfile)
    def handle_profile_notifications(sender, instance, created, **kwargs):
        """Handle user profile-related notifications"""
        try:
            service = NotificationService()
            
            if created:
                # Profile created - send profile completion reminder if incomplete
                completion_percentage = instance.get_completion_percentage()
                if completion_percentage < 100:
                    service.create_notification(
                        recipient=instance.user,
                        notification_type='profile_incomplete',
                        title='Complete Your Profile',
                        message=f'Your profile is {completion_percentage}% complete. Complete your profile to get better doctor recommendations and improved service.',
                        priority='low',
                        content_object=instance
                    )
                    
        except Exception as e:
            logger.error(f"Error handling profile notification for user {instance.user.username}: {str(e)}")


# Appointment reminder signals (for scheduled reminders)
def send_appointment_reminders():
    """Send appointment reminders - called by management command or celery task"""
    if not Appointment:
        return
        
    try:
        from datetime import datetime, timedelta
        from .services import send_appointment_reminder
        
        # Get appointments for tomorrow
        tomorrow = timezone.now().date() + timedelta(days=1)
        upcoming_appointments = Appointment.objects.filter(
            date=tomorrow,
            status__in=['scheduled', 'confirmed']
        ).select_related('patient', 'doctor__user')
        
        reminder_count = 0
        for appointment in upcoming_appointments:
            try:
                send_appointment_reminder(appointment)
                reminder_count += 1
            except Exception as e:
                logger.error(f"Error sending reminder for appointment {appointment.id}: {str(e)}")
        
        logger.info(f"Sent {reminder_count} appointment reminders")
        return reminder_count
        
    except Exception as e:
        logger.error(f"Error in send_appointment_reminders: {str(e)}")
        return 0


# System health notifications
def send_system_health_notifications():
    """Send system health notifications to admins"""
    try:
        from django.db import connection
        from .models import Notification, NotificationQueue
        
        service = NotificationService()
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        
        # Check notification queue health
        failed_notifications = Notification.objects.filter(
            email_status='failed',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        pending_queue_items = NotificationQueue.objects.filter(
            processed=False,
            created_at__lt=timezone.now() - timedelta(hours=1)
        ).count()
        
        # Alert if too many failures
        if failed_notifications > 10:
            for admin in admin_users:
                service.create_notification(
                    recipient=admin,
                    notification_type='system_alert',
                    title='High Notification Failure Rate',
                    message=f'{failed_notifications} notifications failed in the last 24 hours. Please check the notification system.',
                    priority='urgent',
                    extra_data={'failed_count': failed_notifications}
                )
        
        # Alert if queue is backed up
        if pending_queue_items > 50:
            for admin in admin_users:
                service.create_notification(
                    recipient=admin,
                    notification_type='system_alert',
                    title='Notification Queue Backup',
                    message=f'{pending_queue_items} notifications are pending processing. Please check the queue processor.',
                    priority='high',
                    extra_data={'pending_count': pending_queue_items}
                )
                
        logger.info("System health notifications checked")
        
    except Exception as e:
        logger.error(f"Error in send_system_health_notifications: {str(e)}")


# Marketing and engagement notifications
def send_engagement_notifications():
    """Send engagement notifications to inactive users"""
    try:
        service = NotificationService()
        
        # Get users who haven't logged in for 7 days
        inactive_cutoff = timezone.now() - timedelta(days=7)
        inactive_users = User.objects.filter(
            last_login__lt=inactive_cutoff,
            is_active=True
        ).exclude(is_staff=True)
        
        for user in inactive_users:
            # Check if we already sent a re-engagement notification recently
            recent_notification = Notification.objects.filter(
                recipient=user,
                notification_type__name='re_engagement',
                created_at__gte=timezone.now() - timedelta(days=7)
            ).exists()
            
            if not recent_notification:
                service.create_notification(
                    recipient=user,
                    notification_type='re_engagement',
                    title='We miss you at MediCure Plus!',
                    message='It\'s been a while since your last visit. Check out our new features and book your next appointment.',
                    priority='low'
                )
        
        logger.info(f"Sent re-engagement notifications to {inactive_users.count()} users")
        
    except Exception as e:
        logger.error(f"Error in send_engagement_notifications: {str(e)}")


# Health tip notifications
def send_weekly_health_tips():
    """Send weekly health tips to all users"""
    try:
        service = NotificationService()
        
        # Health tips - in production, these would come from a database
        health_tips = [
            "Remember to drink at least 8 glasses of water daily for optimal health.",
            "Regular exercise for 30 minutes daily can significantly improve your cardiovascular health.",
            "A balanced diet with plenty of fruits and vegetables boosts your immune system.",
            "Getting 7-8 hours of quality sleep is essential for mental and physical health.",
            "Regular health checkups can help detect and prevent serious health issues early."
        ]
        
        import random
        tip = random.choice(health_tips)
        
        # Send to all active users
        active_users = User.objects.filter(is_active=True)
        
        notifications = service.bulk_create_notifications(
            recipients=list(active_users),
            notification_type='health_tip',
            title='Weekly Health Tip 💡',
            message=tip,
            priority='low'
        )
        
        logger.info(f"Sent weekly health tips to {len(notifications)} users")
        
    except Exception as e:
        logger.error(f"Error in send_weekly_health_tips: {str(e)}")
