"""
MediCureFlow Admin System Models
Comprehensive models for admin operations, logging, and system management
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json


class AdminActivity(models.Model):
    """Log all admin activities"""
    ACTION_TYPES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export Data'),
        ('bulk_action', 'Bulk Action'),
        ('system_setting', 'System Setting'),
    ]
    
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    
    # Generic foreign key to track any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Store additional data as JSON
    metadata = models.JSONField(default=dict, blank=True)
    
    # Track if the action was successful
    success = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'admin_activities'
        verbose_name = 'Admin Activity'
        verbose_name_plural = 'Admin Activities'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['admin', 'timestamp']),
            models.Index(fields=['action_type']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.admin.username} - {self.action_type} - {self.timestamp}"


class SystemAlert(models.Model):
    """System alerts and notifications for admin"""
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    ALERT_TYPES = [
        ('security', 'Security Alert'),
        ('system', 'System Alert'),
        ('user_activity', 'User Activity'),
        ('doctor_activity', 'Doctor Activity'),
        ('appointment', 'Appointment Alert'),
        ('payment', 'Payment Alert'),
        ('maintenance', 'Maintenance Alert'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    
    # Link to specific object if relevant
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'system_alerts'
        verbose_name = 'System Alert'
        verbose_name_plural = 'System Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['is_read', 'is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.severity})"


class AdminConfiguration(models.Model):
    """Store admin system configurations"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    category = models.CharField(max_length=50, default='general')
    is_sensitive = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'admin_configurations'
        verbose_name = 'Admin Configuration'
        verbose_name_plural = 'Admin Configurations'
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.category}.{self.key}"
    
    def get_value(self):
        """Get typed value based on data_type"""
        if self.data_type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes']
        elif self.data_type == 'integer':
            try:
                return int(self.value)
            except ValueError:
                return 0
        elif self.data_type == 'float':
            try:
                return float(self.value)
            except ValueError:
                return 0.0
        elif self.data_type == 'json':
            try:
                return json.loads(self.value)
            except json.JSONDecodeError:
                return {}
        return self.value
