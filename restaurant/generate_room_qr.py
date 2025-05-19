import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings') # Replace 'myproject.settings' with your project's settings module
django.setup()

import qrcode
import jwt
from datetime import datetime, timedelta

# Secret key for JWT - must match Django's SECRET_KEY
from django.conf import settings

SECRET_KEY = settings.SECRET_KEY

def generate_room_token(room_number):
    # Create a JWT token with room number and expiration
    payload = {
        'room': room_number,
        'exp': datetime.now() + timedelta(hours=24)  # Token expires in 24 hours
    }
    print(f"Generating token for room {room_number}: exp={payload['exp']} now={datetime.now()}")
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

BASE_URL = "http://192.168.15.69:8000/menu/access/"  # Changed URL to use access endpoint

room_numbers = range(101, 122)  # Example: Rooms 101 to 110

for room in room_numbers:
    # Generate secure token for the room
    token = generate_room_token(str(room))
    qr_url = f"{BASE_URL}{token}"
    img = qrcode.make(qr_url)
    img.save(f"room_{room}.png")
    print(f"Generated QR for Room {room}: {qr_url}")