from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    NotificationType, Notification, NotificationPreference,
    NotificationQueue, NotificationLog, NotificationTemplate, DeviceToken
)


@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'description', 'default_email_enabled',
        'default_sms_enabled', 'default_push_enabled', 'created_at'
    ]
    list_filter = [
        'default_email_enabled', 'default_sms_enabled', 'default_push_enabled',
        'created_at'
    ]
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Default Settings', {
            'fields': (
                'default_email_enabled', 'default_sms_enabled', 
                'default_push_enabled'
            )
        }),
        ('Templates', {
            'fields': (
                'email_subject_template', 'email_body_template',
                'sms_template', 'push_title_template', 'push_body_template'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'recipient_link', 'notification_type', 'priority',
        'status_badges', 'is_read_badge', 'created_at'
    ]
    list_filter = [
        'notification_type', 'priority', 'email_status', 'sms_status',
        'push_status', 'created_at'
    ]
    search_fields = [
        'title', 'message', 'recipient__username', 
        'recipient__first_name', 'recipient__last_name'
    ]
    readonly_fields = [
        'created_at', 'sent_at', 'read_at', 'is_read',
        'recipient_link', 'content_object_link'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'recipient_link', 'notification_type', 'title', 
                'message', 'priority'
            )
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id', 'content_object_link'),
            'classes': ('collapse',)
        }),
        ('Extra Data', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Delivery Status', {
            'fields': (
                'email_status', 'sms_status', 'push_status',
                'scheduled_at', 'sent_at'
            )
        }),
        ('Read Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def recipient_link(self, obj):
        if obj.recipient:
            url = reverse('admin:auth_user_change', args=[obj.recipient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.recipient.get_full_name())
        return '-'
    recipient_link.short_description = 'Recipient'
    
    def content_object_link(self, obj):
        if obj.content_object:
            try:
                url = reverse(
                    f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change',
                    args=[obj.object_id]
                )
                return format_html('<a href="{}">{}</a>', url, str(obj.content_object))
            except:
                return str(obj.content_object)
        return '-'
    content_object_link.short_description = 'Related Object'
    
    def status_badges(self, obj):
        badges = []
        
        if obj.email_status == 'sent':
            badges.append('<span class="badge" style="background-color: green; color: white;">Email ✓</span>')
        elif obj.email_status == 'failed':
            badges.append('<span class="badge" style="background-color: red; color: white;">Email ✗</span>')
        
        if obj.sms_status == 'sent':
            badges.append('<span class="badge" style="background-color: green; color: white;">SMS ✓</span>')
        elif obj.sms_status == 'failed':
            badges.append('<span class="badge" style="background-color: red; color: white;">SMS ✗</span>')
        
        if obj.push_status == 'sent':
            badges.append('<span class="badge" style="background-color: green; color: white;">Push ✓</span>')
        elif obj.push_status == 'failed':
            badges.append('<span class="badge" style="background-color: red; color: white;">Push ✗</span>')
        
        return format_html(' '.join(badges)) if badges else '-'
    status_badges.short_description = 'Delivery Status'
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html('<span class="badge" style="background-color: blue; color: white;">Read</span>')
        else:
            return format_html('<span class="badge" style="background-color: orange; color: white;">Unread</span>')
    is_read_badge.short_description = 'Read Status'
    
    actions = ['mark_as_read', 'resend_notifications']
    
    def mark_as_read(self, request, queryset):
        updated = 0
        for notification in queryset:
            if not notification.is_read:
                notification.mark_as_read()
                updated += 1
        
        self.message_user(request, f'Marked {updated} notifications as read.')
    mark_as_read.short_description = 'Mark selected notifications as read'
    
    def resend_notifications(self, request, queryset):
        from .services import NotificationService
        service = NotificationService()
        
        resent = 0
        for notification in queryset:
            try:
                service.queue_notification(notification)
                resent += 1
            except:
                pass
        
        self.message_user(request, f'Re-queued {resent} notifications for delivery.')
    resend_notifications.short_description = 'Re-send selected notifications'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'notification_type', 'email_enabled',
        'sms_enabled', 'push_enabled', 'updated_at'
    ]
    list_filter = [
        'notification_type', 'email_enabled', 'sms_enabled',
        'push_enabled', 'updated_at'
    ]
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'notification_type__name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
        return '-'
    user_link.short_description = 'User'


@admin.register(NotificationQueue)
class NotificationQueueAdmin(admin.ModelAdmin):
    list_display = [
        'notification_link', 'send_email', 'send_sms', 'send_push',
        'attempts', 'processed', 'next_attempt_at', 'created_at'
    ]
    list_filter = [
        'send_email', 'send_sms', 'send_push', 'processed',
        'next_attempt_at', 'created_at'
    ]
    search_fields = ['notification__title', 'notification__recipient__username']
    readonly_fields = ['created_at', 'processed_at']
    date_hierarchy = 'created_at'
    
    def notification_link(self, obj):
        if obj.notification:
            url = reverse('admin:notifications_notification_change', args=[obj.notification.pk])
            return format_html('<a href="{}">{}</a>', url, obj.notification.title)
        return '-'
    notification_link.short_description = 'Notification'
    
    actions = ['requeue_items', 'mark_as_processed']
    
    def requeue_items(self, request, queryset):
        updated = queryset.update(
            processed=False,
            attempts=0,
            next_attempt_at=timezone.now(),
            last_error=''
        )
        self.message_user(request, f'Re-queued {updated} items for processing.')
    requeue_items.short_description = 'Re-queue selected items'
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(
            processed=True,
            processed_at=timezone.now()
        )
        self.message_user(request, f'Marked {updated} items as processed.')
    mark_as_processed.short_description = 'Mark selected items as processed'


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'notification_link', 'action', 'channel', 'timestamp'
    ]
    list_filter = ['action', 'channel', 'timestamp']
    search_fields = [
        'notification__title', 'notification__recipient__username',
        'action', 'channel'
    ]
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def notification_link(self, obj):
        if obj.notification:
            url = reverse('admin:notifications_notification_change', args=[obj.notification.pk])
            return format_html('<a href="{}">{}</a>', url, obj.notification.title)
        return '-'
    notification_link.short_description = 'Notification'


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'notification_type', 'language', 'is_active', 'updated_at'
    ]
    list_filter = ['notification_type', 'language', 'is_active', 'updated_at']
    search_fields = ['name', 'subject_template', 'body_template']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'notification_type', 'language', 'is_active')
        }),
        ('Template Content', {
            'fields': ('subject_template', 'body_template', 'variables')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'platform', 'token_preview', 'is_active',
        'created_at', 'last_used_at'
    ]
    list_filter = ['platform', 'is_active', 'created_at', 'last_used_at']
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'token', 'platform'
    ]
    readonly_fields = ['created_at', 'last_used_at']
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
        return '-'
    user_link.short_description = 'User'
    
    def token_preview(self, obj):
        if obj.token:
            return obj.token[:20] + '...' if len(obj.token) > 20 else obj.token
        return '-'
    token_preview.short_description = 'Token Preview'
    
    actions = ['deactivate_tokens', 'activate_tokens']
    
    def deactivate_tokens(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} device tokens.')
    deactivate_tokens.short_description = 'Deactivate selected tokens'
    
    def activate_tokens(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} device tokens.')
    activate_tokens.short_description = 'Activate selected tokens'


# Custom admin views for statistics
class NotificationAdminSite(admin.AdminSite):
    site_header = 'MediCure Plus Notification Administration'
    site_title = 'Notification Admin'
    index_title = 'Notification System Management'
    
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Add notification statistics to admin index
        extra_context['notification_stats'] = {
            'total_notifications': Notification.objects.count(),
            'unread_notifications': Notification.objects.filter(read_at__isnull=True).count(),
            'failed_notifications': Notification.objects.filter(
                Q(email_status='failed') | Q(sms_status='failed') | Q(push_status='failed')
            ).count(),
            'pending_queue': NotificationQueue.objects.filter(processed=False).count(),
            'notification_types': NotificationType.objects.count(),
            'active_devices': DeviceToken.objects.filter(is_active=True).count(),
        }
        
        return super().index(request, extra_context)


# Register models with custom admin site (optional)
# notification_admin_site = NotificationAdminSite(name='notification_admin')
# notification_admin_site.register(Notification, NotificationAdmin)
# notification_admin_site.register(NotificationType, NotificationTypeAdmin)
# notification_admin_site.register(NotificationPreference, NotificationPreferenceAdmin)
# notification_admin_site.register(NotificationQueue, NotificationQueueAdmin)
# notification_admin_site.register(NotificationLog, NotificationLogAdmin)
# notification_admin_site.register(NotificationTemplate, NotificationTemplateAdmin)
# notification_admin_site.register(DeviceToken, DeviceTokenAdmin)
