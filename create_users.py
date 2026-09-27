"""
Seeds three demo accounts (one per role) so you can log in immediately
after running migrations. Safe to re-run — it skips users that already exist.

Usage:
    python create_users.py
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invisense.settings')
django.setup()

from core.models import User  # noqa: E402

DEMO_USERS = [
    {'username': 'admin', 'password': 'adminpassword', 'role': 'ADMIN', 'superuser': True},
    {'username': 'invigilator1', 'password': 'invpassword', 'role': 'INVIGILATOR', 'superuser': False},
    {'username': 'controlroom', 'password': 'crpassword', 'role': 'CONTROL_ROOM', 'superuser': False},
]

for entry in DEMO_USERS:
    if User.objects.filter(username=entry['username']).exists():
        print(f"Skipped (already exists): {entry['username']}")
        continue

    if entry['superuser']:
        user = User.objects.create_superuser(entry['username'], f"{entry['username']}@example.com", entry['password'])
    else:
        user = User.objects.create_user(entry['username'], f"{entry['username']}@example.com", entry['password'])

    user.role = entry['role']
    user.save()
    print(f"Created {entry['role']} user: {entry['username']} / {entry['password']}")

print("\nDone. Remember to change these passwords before deploying to production.")
