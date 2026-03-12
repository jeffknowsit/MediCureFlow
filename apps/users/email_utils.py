"""
Email notification utilities for the MediCureFlow application.

This module handles sending various types of emails including:
- Appointment confirmations
- Appointment reminders  
- Cancellation notifications
- Welcome emails
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Service class for handling email notifications."""
    
    @staticmethod
    def send_appointment_confirmation(appointment):
        """
        Send appointment confirmation email to patient.
        
        Args:
            appointment: Appointment instance
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            patient = appointment.patient
            doctor = appointment.doctor
            
            subject = f"Appointment Confirmed - {doctor.display_name} on {appointment.appointment_date}"
            
            # Render HTML email template
            html_content = render_to_string('emails/appointment_confirmation.html', {
                'patient': patient,
                'doctor': doctor,
                'appointment': appointment,
                'site_name': 'MediCureFlow'
            })
            
            # Create plain text version
            text_content = strip_tags(html_content)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[patient.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Appointment confirmation email sent to {patient.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send appointment confirmation email: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_reminder(appointment):
        """
        Send appointment reminder email to patient.
        
        Args:
            appointment: Appointment instance
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            patient = appointment.patient
            doctor = appointment.doctor
            
            subject = f"Reminder: Appointment Tomorrow - {doctor.display_name}"
            
            # Render HTML email template
            html_content = render_to_string('emails/appointment_reminder.html', {
                'patient': patient,
                'doctor': doctor,
                'appointment': appointment,
                'site_name': 'MediCureFlow'
            })
            
            # Create plain text version
            text_content = strip_tags(html_content)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[patient.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Appointment reminder email sent to {patient.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send appointment reminder email: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_cancellation(appointment, cancelled_by='system'):
        """
        Send appointment cancellation email to both patient and doctor.
        
        Args:
            appointment: Appointment instance
            cancelled_by: Who cancelled ('patient', 'doctor', 'system')
            
        Returns:
            bool: True if emails sent successfully, False otherwise
        """
        try:
            patient = appointment.patient
            doctor = appointment.doctor
            
            # Send email to patient
            subject_patient = f"Appointment Cancelled - {doctor.display_name} on {appointment.appointment_date}"
            
            html_content_patient = render_to_string('emails/appointment_cancellation_patient.html', {
                'patient': patient,
                'doctor': doctor,
                'appointment': appointment,
                'cancelled_by': cancelled_by,
                'site_name': 'MediCureFlow'
            })
            
            text_content_patient = strip_tags(html_content_patient)
            
            msg_patient = EmailMultiAlternatives(
                subject=subject_patient,
                body=text_content_patient,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[patient.email]
            )
            msg_patient.attach_alternative(html_content_patient, "text/html")
            msg_patient.send()
            
            # Send email to doctor
            subject_doctor = f"Appointment Cancelled - {patient.get_full_name()} on {appointment.appointment_date}"
            
            html_content_doctor = render_to_string('emails/appointment_cancellation_doctor.html', {
                'patient': patient,
                'doctor': doctor,
                'appointment': appointment,
                'cancelled_by': cancelled_by,
                'site_name': 'MediCureFlow'
            })
            
            text_content_doctor = strip_tags(html_content_doctor)
            
            msg_doctor = EmailMultiAlternatives(
                subject=subject_doctor,
                body=text_content_doctor,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[doctor.email]
            )
            msg_doctor.attach_alternative(html_content_doctor, "text/html")
            msg_doctor.send()
            
            logger.info(f"Appointment cancellation emails sent for appointment {appointment.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send appointment cancellation emails: {str(e)}")
            return False
    
    @staticmethod
    def send_welcome_email(user, user_type='patient'):
        """
        Send welcome email to new users.
        
        Args:
            user: User instance
            user_type: 'patient' or 'doctor'
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            subject = f"Welcome to MediCureFlow - Your Healthcare Partner"
            
            template_name = f'emails/welcome_{user_type}.html'
            html_content = render_to_string(template_name, {
                'user': user,
                'site_name': 'MediCureFlow'
            })
            
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Welcome email sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_status_update(appointment, old_status, new_status):
        """
        Send appointment status update email to patient.
        
        Args:
            appointment: Appointment instance
            old_status: Previous status
            new_status: New status
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            patient = appointment.patient
            doctor = appointment.doctor
            
            status_messages = {
                'confirmed': 'confirmed',
                'completed': 'marked as completed',
                'cancelled': 'cancelled',
                'no_show': 'marked as no-show'
            }
            
            status_message = status_messages.get(new_status, new_status)
            
            subject = f"Appointment Update - Your appointment has been {status_message}"
            
            html_content = render_to_string('emails/appointment_status_update.html', {
                'patient': patient,
                'doctor': doctor,
                'appointment': appointment,
                'old_status': old_status,
                'new_status': new_status,
                'status_message': status_message,
                'site_name': 'MediCureFlow'
            })
            
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[patient.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Appointment status update email sent to {patient.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send appointment status update email: {str(e)}")
            return False


def send_bulk_reminders():
    """
    Send appointment reminders for appointments happening tomorrow.
    This function should be called by a cron job or Celery task.
    
    Returns:
        dict: Summary of emails sent
    """
    from apps.doctors.models import Appointment
    from django.utils import timezone
    
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    # Get all appointments for tomorrow that need reminders
    appointments = Appointment.objects.filter(
        appointment_date=tomorrow,
        status__in=['scheduled', 'confirmed']
    ).select_related('patient', 'doctor')
    
    summary = {
        'total_appointments': appointments.count(),
        'emails_sent': 0,
        'errors': 0
    }
    
    for appointment in appointments:
        try:
            if EmailNotificationService.send_appointment_reminder(appointment):
                summary['emails_sent'] += 1
            else:
                summary['errors'] += 1
        except Exception as e:
            logger.error(f"Error sending reminder for appointment {appointment.id}: {str(e)}")
            summary['errors'] += 1
    
    logger.info(f"Bulk reminder summary: {summary}")
    return summary


def send_bulk_follow_ups():
    """
    Send follow-up emails for completed appointments.
    This function should be called by a cron job or Celery task.
    
    Returns:
        dict: Summary of emails sent
    """
    from apps.doctors.models import Appointment
    from django.utils import timezone
    
    # Get appointments completed 1 day ago
    one_day_ago = timezone.now().date() - timedelta(days=1)
    
    appointments = Appointment.objects.filter(
        appointment_date=one_day_ago,
        status='completed'
    ).select_related('patient', 'doctor')
    
    summary = {
        'total_appointments': appointments.count(),
        'emails_sent': 0,
        'errors': 0
    }
    
    for appointment in appointments:
        try:
            # Send follow-up email with review request
            subject = f"How was your appointment with {appointment.doctor.display_name}?"
            
            html_content = render_to_string('emails/appointment_followup.html', {
                'patient': appointment.patient,
                'doctor': appointment.doctor,
                'appointment': appointment,
                'site_name': 'MediCureFlow'
            })
            
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[appointment.patient.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            summary['emails_sent'] += 1
            
        except Exception as e:
            logger.error(f"Error sending follow-up for appointment {appointment.id}: {str(e)}")
            summary['errors'] += 1
    
    logger.info(f"Bulk follow-up summary: {summary}")
    return summary
