import os
import sys
import django
import shutil
import logging

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reboot_api.settings")
django.setup()

from learning.models import LearningSession
from django.conf import settings

# Configure Logger manually to ensure it works
logger = logging.getLogger('stt_debug')
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

print("--- DEBUG START ---")

# 1. Check FFmpeg
ffmpeg_path = shutil.which("ffmpeg")
print(f"FFmpeg Path: {ffmpeg_path}")

# 2. Check Pydub
try:
    from pydub import AudioSegment
    print("Pydub: Installed")
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        print("Pydub Converter Set")
except ImportError:
    print("Pydub: Not Installed")

# 3. Check Latest Session
try:
    latest_session = LearningSession.objects.last()
    if latest_session:
        print(f"Latest Session ID: {latest_session.id}")
        print(f"Is Analyzing: {latest_session.is_analyzing}")
        print(f"YouTube URL: {latest_session.youtube_url}")
        print(f"STT Logs Count: {latest_session.stt_logs.count()}")
    else:
        print("No LearningSession found.")
except Exception as e:
    print(f"Error checking session: {e}")

# 4. Test Logger
logger.debug("Test log from debug_stt.py")
print("Logger test message sent.")

print("--- DEBUG END ---")
