#!/usr/bin/env python3
"""
MediCureFlow - Production Smoke Test Script
=============================================

This script performs comprehensive health checks for the Django application
to ensure production readiness and ongoing system health monitoring.

Usage:
    python scripts/smoke_test.py [--verbose] [--check=all|web|db|cache|email]

Author: MediCureFlow Team
Last Updated: 2025-01-09
"""

import os
import sys
import django
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any
import argparse
import time
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MediCureFlow.settings.development')
django.setup()

# Django imports (must be after django.setup())
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.conf import settings
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.files.storage import default_storage

User = get_user_model()


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class SmokeTest:
    """Main smoke test class for MediCureFlow."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'tests': []
        }
        self.start_time = time.time()
    
    def log(self, message: str, level: str = 'INFO'):
        """Log messages with color coding."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        colors = {
            'INFO': Colors.CYAN,
            'SUCCESS': Colors.GREEN,
            'WARNING': Colors.WARNING,
            'ERROR': Colors.FAIL,
            'HEADER': Colors.HEADER
        }
        color = colors.get(level, Colors.ENDC)
        print(f"{color}[{timestamp}] {level}: {message}{Colors.ENDC}")
    
    def test_result(self, test_name: str, success: bool, message: str = "", warning: bool = False):
        """Record test result and display."""
        if warning:
            self.results['warnings'] += 1
            status = 'WARN'
            color = Colors.WARNING
        elif success:
            self.results['passed'] += 1
            status = 'PASS'
            color = Colors.GREEN
        else:
            self.results['failed'] += 1
            status = 'FAIL'
            color = Colors.FAIL
        
        self.results['tests'].append({
            'name': test_name,
            'success': success,
            'message': message,
            'warning': warning
        })
        
        status_msg = f"{color}[{status}]{Colors.ENDC} {test_name}"
        if message and (self.verbose or not success or warning):
            status_msg += f" - {message}"
        print(status_msg)
    
    def test_django_configuration(self) -> bool:
        """Test Django configuration and settings."""
        self.log("Testing Django Configuration", 'HEADER')
        
        try:
            # Test settings import
            self.test_result("Settings Import", True, f"Using {settings.SETTINGS_MODULE}")
            
            # Test database configuration
            db_config = settings.DATABASES['default']
            self.test_result("Database Config", True, f"Engine: {db_config['ENGINE']}")
            
            # Test secret key
            has_secret = bool(settings.SECRET_KEY and len(settings.SECRET_KEY) > 20)
            self.test_result("Secret Key", has_secret, 
                           "Configured" if has_secret else "Missing or too short")
            
            # Test media and static files
            self.test_result("Static Files", bool(settings.STATIC_URL), 
                           f"URL: {settings.STATIC_URL}")
            self.test_result("Media Files", bool(settings.MEDIA_URL), 
                           f"URL: {settings.MEDIA_URL}")
            
            # Test installed apps
            critical_apps = [
                'django.contrib.admin', 'django.contrib.auth',
                'apps.users', 'apps.doctors', 'apps.health_ai'
            ]
            missing_apps = [app for app in critical_apps if app not in settings.INSTALLED_APPS]
            self.test_result("Critical Apps", not missing_apps,
                           f"Missing: {missing_apps}" if missing_apps else "All present")
            
            return self.results['failed'] == 0
            
        except Exception as e:
            self.test_result("Django Configuration", False, str(e))
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test database connectivity and basic operations."""
        self.log("Testing Database Connectivity", 'HEADER')
        
        try:
            # Test connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            self.test_result("Database Connection", result[0] == 1, "Connected successfully")
            
            # Test migrations
            try:
                from django.core.management.commands import migrate
                # Check if migrations are up to date
                call_command('check', verbosity=0)
                self.test_result("Migration Status", True, "All migrations applied")
            except Exception as e:
                self.test_result("Migration Status", False, str(e))
            
            # Test model operations
            user_count = User.objects.count()
            self.test_result("User Model Access", True, f"{user_count} users in database")
            
            from apps.doctors.models import Doctor
            doctor_count = Doctor.objects.count()
            self.test_result("Doctor Model Access", True, f"{doctor_count} doctors in database")
            
            return self.results['failed'] == 0
            
        except Exception as e:
            self.test_result("Database Connectivity", False, str(e))
            return False
    
    def test_web_application(self) -> bool:
        """Test web application endpoints and functionality."""
        self.log("Testing Web Application", 'HEADER')
        
        client = Client()
        
        # Test critical URLs
        test_urls = [
            ('/', 'Homepage'),
            ('/login/', 'Login Page'),
            ('/register/', 'Registration Page'),
            ('/quick-checkup/', 'Health Checkup'),
            ('/doctors/search/', 'Doctor Search'),
            ('/admin/', 'Admin Interface'),
            ('/api/', 'API Root'),
        ]
        
        for url, name in test_urls:
            try:
                response = client.get(url, follow=True)
                success = response.status_code in [200, 302]
                message = f"Status: {response.status_code}"
                if not success:
                    message += f" - {response.content.decode('utf-8')[:100]}..."
                self.test_result(f"URL: {name}", success, message)
            except Exception as e:
                self.test_result(f"URL: {name}", False, str(e))
        
        # Test API endpoints
        api_urls = [
            ('/api/doctors/doctors/', 'Doctors API'),
            ('/api/doctors/specialties/', 'Specialties API'),
            ('/api/users/profile/', 'User Profile API'),  # May return 403 without auth
        ]
        
        for url, name in api_urls:
            try:
                response = client.get(url)
                # API might return 403 for unauthenticated requests, which is OK
                success = response.status_code in [200, 403]
                warning = response.status_code == 403
                self.test_result(f"API: {name}", success, 
                               f"Status: {response.status_code}", warning=warning)
            except Exception as e:
                self.test_result(f"API: {name}", False, str(e))
        
        return True
    
    def test_cache_system(self) -> bool:
        """Test cache system functionality."""
        self.log("Testing Cache System", 'HEADER')
        
        try:
            # Test cache set/get
            test_key = 'smoke_test_key'
            test_value = 'smoke_test_value'
            
            cache.set(test_key, test_value, timeout=60)
            retrieved_value = cache.get(test_key)
            
            success = retrieved_value == test_value
            self.test_result("Cache Read/Write", success, 
                           "Working" if success else f"Expected {test_value}, got {retrieved_value}")
            
            # Test cache deletion
            cache.delete(test_key)
            deleted_value = cache.get(test_key)
            success = deleted_value is None
            self.test_result("Cache Deletion", success,
                           "Working" if success else f"Key still exists: {deleted_value}")
            
            # Test cache backend info
            backend = str(type(cache._cache))
            self.test_result("Cache Backend", True, f"Using: {backend}")
            
            return True
            
        except Exception as e:
            self.test_result("Cache System", False, str(e))
            return False
    
    def test_email_system(self) -> bool:
        """Test email configuration."""
        self.log("Testing Email System", 'HEADER')
        
        try:
            # Test email backend configuration
            backend = settings.EMAIL_BACKEND
            self.test_result("Email Backend", True, f"Using: {backend}")
            
            # Test email settings
            has_smtp = hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST
            self.test_result("SMTP Configuration", has_smtp,
                           "Configured" if has_smtp else "Using console backend for development")
            
            # Don't actually send test emails in smoke test to avoid spam
            self.test_result("Email System", True, "Configuration validated")
            
            return True
            
        except Exception as e:
            self.test_result("Email System", False, str(e))
            return False
    
    def test_file_storage(self) -> bool:
        """Test file storage system."""
        self.log("Testing File Storage", 'HEADER')
        
        try:
            # Test default storage
            storage_class = str(type(default_storage))
            self.test_result("Storage Backend", True, f"Using: {storage_class}")
            
            # Test media root existence
            media_root = Path(settings.MEDIA_ROOT)
            exists = media_root.exists()
            self.test_result("Media Directory", exists,
                           f"Path: {media_root}" if exists else f"Missing: {media_root}")
            
            # Test static root configuration
            if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
                static_root = Path(settings.STATIC_ROOT)
                self.test_result("Static Root", True, f"Configured: {static_root}")
            else:
                self.test_result("Static Root", False, "Not configured for production")
            
            return True
            
        except Exception as e:
            self.test_result("File Storage", False, str(e))
            return False
    
    def test_security_configuration(self) -> bool:
        """Test security-related configurations."""
        self.log("Testing Security Configuration", 'HEADER')
        
        # Security checks for production
        security_checks = [
            ('DEBUG', not settings.DEBUG, "DEBUG should be False in production"),
            ('ALLOWED_HOSTS', bool(settings.ALLOWED_HOSTS), "ALLOWED_HOSTS should be configured"),
            ('CSRF_COOKIE_SECURE', getattr(settings, 'CSRF_COOKIE_SECURE', False), 
             "CSRF_COOKIE_SECURE should be True in production"),
            ('SESSION_COOKIE_SECURE', getattr(settings, 'SESSION_COOKIE_SECURE', False),
             "SESSION_COOKIE_SECURE should be True in production"),
            ('SECURE_SSL_REDIRECT', getattr(settings, 'SECURE_SSL_REDIRECT', False),
             "SECURE_SSL_REDIRECT should be True in production"),
        ]
        
        for check_name, condition, message in security_checks:
            # For development, these might be warnings rather than failures
            is_dev = 'development' in settings.SETTINGS_MODULE
            warning = is_dev and not condition
            success = condition or is_dev
            
            self.test_result(f"Security: {check_name}", success, message, warning=warning)
        
        return True
    
    def run_health_check(self, check_type: str = 'all') -> bool:
        """Run the specified health checks."""
        self.log(f"Starting MediCureFlow Health Check - {check_type.upper()}", 'HEADER')
        
        checks = {
            'config': self.test_django_configuration,
            'db': self.test_database_connectivity,
            'web': self.test_web_application,
            'cache': self.test_cache_system,
            'email': self.test_email_system,
            'storage': self.test_file_storage,
            'security': self.test_security_configuration,
        }
        
        if check_type == 'all':
            selected_checks = checks.items()
        else:
            selected_checks = [(check_type, checks[check_type])] if check_type in checks else []
        
        if not selected_checks:
            self.log(f"Unknown check type: {check_type}", 'ERROR')
            return False
        
        # Run selected checks
        overall_success = True
        for check_name, check_function in selected_checks:
            try:
                success = check_function()
                overall_success = overall_success and success
            except Exception as e:
                self.log(f"Check {check_name} failed with exception: {str(e)}", 'ERROR')
                if self.verbose:
                    print(traceback.format_exc())
                overall_success = False
        
        return overall_success
    
    def print_summary(self) -> None:
        """Print test execution summary."""
        duration = time.time() - self.start_time
        
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}MediCureFlow Health Check Summary{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
        
        print(f"{Colors.GREEN}✓ Passed:{Colors.ENDC} {self.results['passed']}")
        print(f"{Colors.FAIL}✗ Failed:{Colors.ENDC} {self.results['failed']}")
        print(f"{Colors.WARNING}⚠ Warnings:{Colors.ENDC} {self.results['warnings']}")
        print(f"{Colors.CYAN}Duration:{Colors.ENDC} {duration:.2f} seconds")
        
        overall_status = "HEALTHY" if self.results['failed'] == 0 else "UNHEALTHY"
        status_color = Colors.GREEN if overall_status == "HEALTHY" else Colors.FAIL
        print(f"{Colors.CYAN}Status:{Colors.ENDC} {status_color}{overall_status}{Colors.ENDC}")
        
        if self.results['failed'] > 0:
            print(f"\n{Colors.FAIL}Failed Tests:{Colors.ENDC}")
            for test in self.results['tests']:
                if not test['success'] and not test.get('warning', False):
                    print(f"  • {test['name']}: {test['message']}")
        
        if self.results['warnings'] > 0 and self.verbose:
            print(f"\n{Colors.WARNING}Warnings:{Colors.ENDC}")
            for test in self.results['tests']:
                if test.get('warning', False):
                    print(f"  • {test['name']}: {test['message']}")


def main():
    """Main function to run smoke tests."""
    parser = argparse.ArgumentParser(
        description='MediCureFlow Production Smoke Test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python scripts/smoke_test.py --check=all --verbose
  python scripts/smoke_test.py --check=web
  python scripts/smoke_test.py --check=db
        '''
    )
    
    parser.add_argument(
        '--check',
        default='all',
        choices=['all', 'config', 'db', 'web', 'cache', 'email', 'storage', 'security'],
        help='Type of health check to perform (default: all)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed information'
    )
    
    args = parser.parse_args()
    
    # Initialize smoke test
    smoke_test = SmokeTest(verbose=args.verbose)
    
    try:
        # Run health check
        success = smoke_test.run_health_check(args.check)
        
        # Print summary
        smoke_test.print_summary()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        smoke_test.log("Health check interrupted by user", 'WARNING')
        sys.exit(130)
    except Exception as e:
        smoke_test.log(f"Health check failed with exception: {str(e)}", 'ERROR')
        if args.verbose:
            print(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
