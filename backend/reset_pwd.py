import os
import django
import sys

# 프로젝트 루트를 sys.path에 추가 (현재 위치가 backend라고 가정)
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from django.contrib.auth import get_user_model

User = get_user_model()
username = 'testuser'
password = 'testpass123'

try:
    user = User.objects.get(username=username)
    user.set_password(password)
    user.save()
    print(f"SUCCESS: User '{username}' found. Password has been reset to '{password}'.")
except User.DoesNotExist:
    print(f"User '{username}' not found. Creating new user...")
    try:
        User.objects.create_user(username=username, password=password)
        print(f"SUCCESS: User '{username}' created with password '{password}'.")
    except Exception as e:
        print(f"ERROR: Failed to create user: {e}")
except Exception as e:
    print(f"ERROR: An unexpected error occurred: {e}")
