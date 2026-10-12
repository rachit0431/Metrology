
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

accounts = {
    "admin": "DEMO_ADMIN_PASSWORD",
    "gatc_pune_lab": "DEMO_GATC_PASSWORD",
    "officer_sharma": "DEMO_LMO_PASSWORD",
}

for username, env_name in accounts.items():
    password = os.environ.get(env_name)

    if not password:
        print(f"Skipped {username}: password not configured")
        continue

    try:
        user = User.objects.get(username=username)
        user.set_password(password)
        user.save(update_fields=["password"])
        print(f"Password reset successfully: {username}")

    except User.DoesNotExist:
        print(f"Account not found: {username}")
