"""
Django signals for doctors app.

This module contains signal handlers for appointment notifications,
doctor profile updates, and automated tasks.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Doctor, Appointment, Review
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Appointment)
def send_appointment_notifications(sender, instance, created, **kwargs):
    """
    Send email notifications when appointments are created or updated.
    """
    if created:
        # Send confirmation to patient
        send_appointment_confirmation_to_patient(instance)
        # Send notification to doctor
        send_appointment_notification_to_doctor(instance)
    else:
        # Send update notifications if status changed
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'status' in update_fields:
            send_appointment_status_update(instance)


def send_appointment_confirmation_to_patient(appointment):
    """
    Send appointment confirmation email to patient.
    """
    if not appointment.patient.email:
        return
    
    try:
        subject = f'Appointment Confirmation - {appointment.doctor.display_name}'
        message = f'''
        Dear {appointment.patient.get_full_name() or appointment.patient.username},
        
        Your appointment has been successfully booked!
        
        Appointment Details:
        - Doctor: {appointment.doctor.display_name}
        - Specialty: {appointment.doctor.get_specialty_display()}
        - Date: {appointment.appointment_date}
        - Time: {appointment.appointment_time}
        - Duration: {appointment.duration_minutes} minutes
        - Fee: ₹{appointment.fee_charged}
        
        Location:
        {appointment.doctor.address}
        {appointment.doctor.city}, {appointment.doctor.state}
        
        Contact: {appointment.doctor.phone}
        
        Please arrive 15 minutes before your scheduled appointment time.
        
        If you need to reschedule or cancel, please contact us at least 24 hours in advance.
        
        Best regards,
        MediCureFlow Team
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [appointment.patient.email],
            fail_silently=False,
        )
        
        logger.info(f'Appointment confirmation sent to patient: {appointment.patient.email}')
        
    except Exception as e:
        logger.error(f'Error sending appointment confirmation: {e}')


def send_appointment_notification_to_doctor(appointment):
    """
    Send appointment notification email to doctor.
    """
    if not appointment.doctor.email:
        return
    
    try:
        subject = f'New Appointment Booking - {appointment.appointment_date}'
        message = f'''
        Dear Dr. {appointment.doctor.full_name},
        
        You have a new appointment booking!
        
        Patient Details:
        - Name: {appointment.patient.get_full_name() or appointment.patient.username}
        - Email: {appointment.patient.email}
        - Phone: {appointment.patient_phone or 'Not provided'}
        
        Appointment Details:
        - Date: {appointment.appointment_date}
        - Time: {appointment.appointment_time}
        - Duration: {appointment.duration_minutes} minutes
        
        Patient Notes:
        {appointment.patient_notes or 'No additional notes'}
        
        You can manage this appointment through your doctor dashboard.
        
        Best regards,
        MediCureFlow Team
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [appointment.doctor.email],
            fail_silently=False,
        )
        
        logger.info(f'Appointment notification sent to doctor: {appointment.doctor.email}')
        
    except Exception as e:
        logger.error(f'Error sending doctor notification: {e}')


def send_appointment_status_update(appointment):
    """
    Send status update email to patient when appointment status changes.
    """
    if not appointment.patient.email:
        return
    
    try:
        status_messages = {
            'confirmed': 'Your appointment has been confirmed by the doctor.',
            'in_progress': 'Your appointment is currently in progress.',
            'completed': 'Your appointment has been completed.',
            'cancelled': 'Your appointment has been cancelled.',
            'no_show': 'You were marked as no-show for your appointment.',
        }
        
        status_message = status_messages.get(appointment.status, 'Your appointment status has been updated.')
        
        subject = f'Appointment Status Update - {appointment.doctor.display_name}'
        message = f'''
        Dear {appointment.patient.get_full_name() or appointment.patient.username},
        
        {status_message}
        
        Appointment Details:
        - Doctor: {appointment.doctor.display_name}
        - Date: {appointment.appointment_date}
        - Time: {appointment.appointment_time}
        - Status: {appointment.get_status_display()}
        
        {appointment.doctor_notes if appointment.doctor_notes else ''}
        
        If you have any questions, please contact us.
        
        Best regards,
        MediCureFlow Team
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [appointment.patient.email],
            fail_silently=False,
        )
        
        logger.info(f'Status update sent to patient: {appointment.patient.email}')
        
    except Exception as e:
        logger.error(f'Error sending status update: {e}')


@receiver(post_save, sender=Review)
def notify_doctor_of_review(sender, instance, created, **kwargs):
    """
    Notify doctor when they receive a new review.
    """
    if created and instance.doctor.email:
        try:
            subject = f'New Review Received - {instance.rating} Stars'
            message = f'''
            Dear Dr. {instance.doctor.full_name},
            
            You have received a new review!
            
            Rating: {instance.rating} out of 5 stars
            Title: {instance.title or 'No title'}
            
            Review:
            {instance.comment}
            
            Reviewer: {instance.patient.get_full_name() or instance.patient.username}
            Date: {instance.created_at.strftime('%B %d, %Y')}
            
            You can view all your reviews in your doctor dashboard.
            
            Best regards,
            MediCureFlow Team
            '''
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.doctor.email],
                fail_silently=False,
            )
            
            logger.info(f'Review notification sent to doctor: {instance.doctor.email}')
            
        except Exception as e:
            logger.error(f'Error sending review notification: {e}')
