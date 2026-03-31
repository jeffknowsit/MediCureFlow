import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MediCureFlow.settings')
django.setup()

from apps.doctors.models import Doctor

with open('doctors_credentials_list.md', 'w', encoding='utf-8') as f:
    for d in Doctor.objects.all():
        f.write(f"* **{d.first_name} {d.last_name}** ({d.get_specialty_display()})\n  Username: `{d.user.username}`\n  Password: `12345678`\n\n")
