from django.apps import AppConfig


class AdminSystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.admin_system'
    verbose_name = 'MediCureFlow Admin System'
    
    def ready(self):
        """Initialize admin system on startup"""
        import apps.admin_system.signals
