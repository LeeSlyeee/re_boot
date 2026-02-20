import os
import django
from django.db import connection

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reboot_api.settings")
django.setup()

def check_table():
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'learning_learningsession' ORDER BY ordinal_position")
        columns = cursor.fetchall()
        print(f"{'Column':<30} | {'Type':<20} | {'Null?':<10} | {'Default'}")
        print("-" * 80)
        for col in columns:
            print(f"{col[0]:<30} | {col[1]:<20} | {col[2]:<10} | {col[3]}")

if __name__ == "__main__":
    check_table()
