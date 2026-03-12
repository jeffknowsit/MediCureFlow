from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.template import Template, Context
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from .models import (
    Notification, NotificationQueue, NotificationLog, 
    NotificationPreference, NotificationType, DeviceToken
)
import logging
import json
import requests
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class NotificationService:
    """Core service for handling all notification operations"""
    
    def __init__(self):
        self.email_backend = EmailNotificationService()
        self.sms_backend = SMSNotificationService()
        self.push_backend = PushNotificationService()
    
    def create_notification(
        self,
        recipient: User,
        notification_type: str,
        title: str,
        message: str,
        priority: str = 'normal',
        content_object=None,
        extra_data: Dict = None,
        scheduled_at=None,
        send_immediately: bool = True
    ) -> Notification:
        """Create a new notification"""
        
        try:
            # Get or create notification type
            notif_type, created = NotificationType.objects.get_or_create(
                name=notification_type,
                defaults={
                    'description': f'Auto-created notification type: {notification_type}',
                    'default_email_enabled': True,
                    'default_sms_enabled': False,
                    'default_push_enabled': True,
                }
            )
            
            # Create notification
            notification = Notification.objects.create(
                recipient=recipient,
                notification_type=notif_type,
                title=title,
                message=message,
                priority=priority,
                content_object=content_object,
                extra_data=extra_data or {},
                scheduled_at=scheduled_at or timezone.now()
            )
            
            # Log creation
            NotificationLog.objects.create(
                notification=notification,
                action='created',
                channel='system',
                details={'created_by': 'system'}
            )
            
            if send_immediately:
                self.queue_notification(notification)
            
            logger.info(f"Created notification {notification.id} for {recipient.username}")
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            raise
    
    def queue_notification(self, notification: Notification):
        """Queue notification for delivery"""
        
        try:
            # Get user preferences
            preferences = self._get_user_preferences(notification.recipient, notification.notification_type)
            
            # Create queue entry
            queue_entry = NotificationQueue.objects.create(
                notification=notification,
                send_email=preferences.get('email', True),
                send_sms=preferences.get('sms', False),
                send_push=preferences.get('push', True)
            )
            
            # Log queuing
            NotificationLog.objects.create(
                notification=notification,
                action='queued',
                channel='system',
                details={'queue_id': queue_entry.id}
            )
            
            logger.info(f"Queued notification {notification.id}")
            
        except Exception as e:
            logger.error(f"Error queuing notification {notification.id}: {str(e)}")
    
    def process_queue(self, max_notifications: int = 50):
        """Process queued notifications"""
        
        queued_notifications = NotificationQueue.objects.filter(
            processed=False,
            next_attempt_at__lte=timezone.now()
        )[:max_notifications]
        
        processed_count = 0
        
        for queue_entry in queued_notifications:
            try:
                success = self._process_single_notification(queue_entry)
                if success:
                    queue_entry.processed = True
                    queue_entry.processed_at = timezone.now()
                    queue_entry.save()
                    processed_count += 1
                else:
                    queue_entry.increment_attempts("Processing failed")
                    
            except Exception as e:
                logger.error(f"Error processing notification {queue_entry.notification.id}: {str(e)}")
                queue_entry.increment_attempts(str(e))
        
        logger.info(f"Processed {processed_count} notifications")
        return processed_count
    
    def _process_single_notification(self, queue_entry: NotificationQueue) -> bool:
        """Process a single notification from the queue"""
        
        notification = queue_entry.notification
        success_count = 0
        total_channels = 0
        
        # Send email
        if queue_entry.send_email:
            total_channels += 1
            try:
                success = self.email_backend.send_notification(notification)
                if success:
                    notification.email_status = 'sent'
                    success_count += 1
                else:
                    notification.email_status = 'failed'
            except Exception as e:
                logger.error(f"Email sending failed for notification {notification.id}: {str(e)}")
                notification.email_status = 'failed'
        
        # Send SMS
        if queue_entry.send_sms:
            total_channels += 1
            try:
                success = self.sms_backend.send_notification(notification)
                if success:
                    notification.sms_status = 'sent'
                    success_count += 1
                else:
                    notification.sms_status = 'failed'
            except Exception as e:
                logger.error(f"SMS sending failed for notification {notification.id}: {str(e)}")
                notification.sms_status = 'failed'
        
        # Send push notification
        if queue_entry.send_push:
            total_channels += 1
            try:
                success = self.push_backend.send_notification(notification)
                if success:
                    notification.push_status = 'sent'
                    success_count += 1
                else:
                    notification.push_status = 'failed'
            except Exception as e:
                logger.error(f"Push notification failed for notification {notification.id}: {str(e)}")
                notification.push_status = 'failed'
        
        # Update notification timestamp
        if success_count > 0:
            notification.sent_at = timezone.now()
        
        notification.save()
        
        # Return True if at least one channel succeeded
        return success_count > 0
    
    def _get_user_preferences(self, user: User, notification_type: NotificationType) -> Dict[str, bool]:
        """Get user preferences for a notification type"""
        
        try:
            preference = NotificationPreference.objects.get(
                user=user,
                notification_type=notification_type
            )
            return {
                'email': preference.email_enabled,
                'sms': preference.sms_enabled,
                'push': preference.push_enabled,
            }
        except NotificationPreference.DoesNotExist:
            # Use default preferences from notification type
            return {
                'email': notification_type.default_email_enabled,
                'sms': notification_type.default_sms_enabled,
                'push': notification_type.default_push_enabled,
            }
    
    def bulk_create_notifications(
        self,
        recipients: List[User],
        notification_type: str,
        title: str,
        message: str,
        **kwargs
    ) -> List[Notification]:
        """Create notifications for multiple users"""
        
        notifications = []
        
        for recipient in recipients:
            try:
                notification = self.create_notification(
                    recipient=recipient,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    send_immediately=False,  # Queue all at once
                    **kwargs
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Error creating notification for {recipient.username}: {str(e)}")
        
        # Queue all notifications
        for notification in notifications:
            self.queue_notification(notification)
        
        logger.info(f"Created {len(notifications)} bulk notifications")
        return notifications


class EmailNotificationService:
    """Service for sending email notifications"""
    
    def send_notification(self, notification: Notification) -> bool:
        """Send email notification"""
        
        try:
            recipient_email = self._get_recipient_email(notification.recipient)
            if not recipient_email:
                logger.warning(f"No email found for user {notification.recipient.username}")
                return False
            
            # Prepare email content
            subject = self._render_template(
                notification.notification_type.email_subject_template or notification.title,
                notification
            )
            
            body = self._render_template(
                notification.notification_type.email_body_template or notification.message,
                notification
            )
            
            # Send email
            success = send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False
            )
            
            # Log the attempt
            NotificationLog.objects.create(
                notification=notification,
                action='sent' if success else 'failed',
                channel='email',
                details={
                    'recipient_email': recipient_email,
                    'subject': subject
                }
            )
            
            return bool(success)
            
        except Exception as e:
            logger.error(f"Error sending email for notification {notification.id}: {str(e)}")
            NotificationLog.objects.create(
                notification=notification,
                action='failed',
                channel='email',
                details={'error': str(e)}
            )
            return False
    
    def _get_recipient_email(self, user: User) -> Optional[str]:
        """Get user's email address"""
        return user.email if user.email else None
    
    def _render_template(self, template_string: str, notification: Notification) -> str:
        """Render template with notification context"""
        if not template_string:
            return ""
        
        template = Template(template_string)
        context = Context({
            'user': notification.recipient,
            'notification': notification,
            'title': notification.title,
            'message': notification.message,
            'extra_data': notification.extra_data,
        })
        
        return template.render(context)


class SMSNotificationService:
    """Service for sending SMS notifications"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'SMS_API_KEY', None)
        self.api_url = getattr(settings, 'SMS_API_URL', None)
        self.sender_id = getattr(settings, 'SMS_SENDER_ID', 'MediCure')
    
    def send_notification(self, notification: Notification) -> bool:
        """Send SMS notification"""
        
        if not self.api_key or not self.api_url:
            logger.warning("SMS API not configured")
            return False
        
        try:
            phone_number = self._get_recipient_phone(notification.recipient)
            if not phone_number:
                logger.warning(f"No phone number found for user {notification.recipient.username}")
                return False
            
            # Prepare SMS content
            message = self._render_template(
                notification.notification_type.sms_template or notification.message,
                notification
            )
            
            # Truncate message to SMS limit
            message = message[:160] if len(message) > 160 else message
            
            # Send SMS via API (example implementation)
            success = self._send_sms_api(phone_number, message)
            
            # Log the attempt
            NotificationLog.objects.create(
                notification=notification,
                action='sent' if success else 'failed',
                channel='sms',
                details={
                    'recipient_phone': phone_number,
                    'message_length': len(message)
                }
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending SMS for notification {notification.id}: {str(e)}")
            NotificationLog.objects.create(
                notification=notification,
                action='failed',
                channel='sms',
                details={'error': str(e)}
            )
            return False
    
    def _get_recipient_phone(self, user: User) -> Optional[str]:
        """Get user's phone number"""
        try:
            if hasattr(user, 'userprofile') and user.userprofile.phone:
                return user.userprofile.phone
            elif hasattr(user, 'doctor') and user.doctor.phone:
                return user.doctor.phone
            return None
        except:
            return None
    
    def _send_sms_api(self, phone_number: str, message: str) -> bool:
        """Send SMS via external API"""
        try:
            # Example API call - replace with your SMS provider
            data = {
                'api_key': self.api_key,
                'sender': self.sender_id,
                'to': phone_number,
                'message': message
            }
            
            response = requests.post(self.api_url, data=data, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"SMS API error: {str(e)}")
            return False
    
    def _render_template(self, template_string: str, notification: Notification) -> str:
        """Render SMS template"""
        if not template_string:
            return ""
        
        template = Template(template_string)
        context = Context({
            'user': notification.recipient,
            'notification': notification,
            'title': notification.title,
            'message': notification.message,
        })
        
        return template.render(context)


class PushNotificationService:
    """Service for sending push notifications"""
    
    def __init__(self):
        self.fcm_server_key = getattr(settings, 'FCM_SERVER_KEY', None)
        self.fcm_url = 'https://fcm.googleapis.com/fcm/send'
    
    def send_notification(self, notification: Notification) -> bool:
        """Send push notification"""
        
        if not self.fcm_server_key:
            logger.warning("FCM not configured")
            return False
        
        try:
            # Get user's device tokens
            device_tokens = DeviceToken.objects.filter(
                user=notification.recipient,
                is_active=True
            )
            
            if not device_tokens.exists():
                logger.warning(f"No device tokens found for user {notification.recipient.username}")
                return False
            
            success_count = 0
            
            for device_token in device_tokens:
                try:
                    success = self._send_push_to_device(device_token, notification)
                    if success:
                        success_count += 1
                        device_token.last_used_at = timezone.now()
                        device_token.save()
                    else:
                        # Mark token as inactive if push failed
                        device_token.is_active = False
                        device_token.save()
                        
                except Exception as e:
                    logger.error(f"Error sending push to device {device_token.id}: {str(e)}")
            
            # Log the attempt
            NotificationLog.objects.create(
                notification=notification,
                action='sent' if success_count > 0 else 'failed',
                channel='push',
                details={
                    'devices_targeted': device_tokens.count(),
                    'devices_reached': success_count
                }
            )
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending push notification {notification.id}: {str(e)}")
            NotificationLog.objects.create(
                notification=notification,
                action='failed',
                channel='push',
                details={'error': str(e)}
            )
            return False
    
    def _send_push_to_device(self, device_token: DeviceToken, notification: Notification) -> bool:
        """Send push notification to a specific device"""
        try:
            # Prepare push data
            title = notification.notification_type.push_title_template or notification.title
            body = notification.notification_type.push_body_template or notification.message
            
            data = {
                'to': device_token.token,
                'notification': {
                    'title': title,
                    'body': body,
                    'icon': '/static/images/icon-192x192.png',
                    'click_action': self._get_click_action(notification)
                },
                'data': {
                    'notification_id': str(notification.id),
                    'type': notification.notification_type.name,
                    'priority': notification.priority,
                    **notification.extra_data
                }
            }
            
            headers = {
                'Authorization': f'key={self.fcm_server_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.fcm_url,
                data=json.dumps(data),
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"FCM API error: {str(e)}")
            return False
    
    def _get_click_action(self, notification: Notification) -> str:
        """Get the click action URL for the notification"""
        if notification.content_object:
            # Generate URL based on content object type
            if hasattr(notification.content_object, 'get_absolute_url'):
                return notification.content_object.get_absolute_url()
        
        # Default to notifications page
        return '/notifications/'


# Utility functions for common notification patterns

def send_appointment_reminder(appointment):
    """Send appointment reminder notification"""
    service = NotificationService()
    
    # For patient
    service.create_notification(
        recipient=appointment.patient,
        notification_type='appointment_reminder',
        title=f'Appointment Reminder - Dr. {appointment.doctor.user.get_full_name()}',
        message=f'Your appointment is scheduled for {appointment.date} at {appointment.time}.',
        priority='high',
        content_object=appointment,
        extra_data={
            'appointment_id': appointment.id,
            'doctor_name': appointment.doctor.user.get_full_name(),
            'appointment_date': appointment.date.isoformat(),
            'appointment_time': appointment.time.isoformat()
        }
    )
    
    # For doctor
    service.create_notification(
        recipient=appointment.doctor.user,
        notification_type='appointment_reminder',
        title=f'Appointment Reminder - {appointment.patient.get_full_name()}',
        message=f'You have an appointment with {appointment.patient.get_full_name()} on {appointment.date} at {appointment.time}.',
        priority='high',
        content_object=appointment,
        extra_data={
            'appointment_id': appointment.id,
            'patient_name': appointment.patient.get_full_name(),
            'appointment_date': appointment.date.isoformat(),
            'appointment_time': appointment.time.isoformat()
        }
    )


def send_appointment_confirmation(appointment):
    """Send appointment confirmation notification"""
    service = NotificationService()
    
    # For patient
    service.create_notification(
        recipient=appointment.patient,
        notification_type='appointment_confirmed',
        title='Appointment Confirmed',
        message=f'Your appointment with Dr. {appointment.doctor.user.get_full_name()} has been confirmed for {appointment.date} at {appointment.time}.',
        priority='normal',
        content_object=appointment,
        extra_data={
            'appointment_id': appointment.id,
            'doctor_name': appointment.doctor.user.get_full_name(),
        }
    )


def send_appointment_cancelled(appointment, cancelled_by_doctor=False):
    """Send appointment cancellation notification"""
    service = NotificationService()
    
    if cancelled_by_doctor:
        # Notify patient
        service.create_notification(
            recipient=appointment.patient,
            notification_type='appointment_cancelled',
            title='Appointment Cancelled',
            message=f'Your appointment with Dr. {appointment.doctor.user.get_full_name()} on {appointment.date} has been cancelled.',
            priority='high',
            content_object=appointment,
        )
    else:
        # Notify doctor
        service.create_notification(
            recipient=appointment.doctor.user,
            notification_type='appointment_cancelled',
            title='Appointment Cancelled',
            message=f'Your appointment with {appointment.patient.get_full_name()} on {appointment.date} has been cancelled.',
            priority='normal',
            content_object=appointment,
        )


def send_welcome_message(user, user_type='patient'):
    """Send welcome message to new users"""
    service = NotificationService()
    
    title = f'Welcome to MediCure Plus, {user.get_full_name()}!'
    
    if user_type == 'patient':
        message = 'Thank you for joining MediCure Plus. You can now book appointments with qualified doctors and access our health checkup system.'
    else:
        message = 'Thank you for joining MediCure Plus as a healthcare provider. You can now manage your appointments and connect with patients.'
    
    service.create_notification(
        recipient=user,
        notification_type='welcome',
        title=title,
        message=message,
        priority='normal'
    )
