import os
import sys
import django
from PIL import Image, ImageDraw, ImageFont
import textwrap

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_dir)

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

import qrcode
import jwt
from datetime import datetime, timedelta
from django.conf import settings

# Constants
SECRET_KEY = settings.SECRET_KEY
BASE_URL = "http://192.168.15.67:8000/menu/access/"
FONT_PATH = "arial.ttf"  # Make sure you have this font or change to a system font
LOGO_PATH = os.path.join(settings.STATIC_ROOT, 'images', 'qr.png')  # Update with your logo path

def generate_room_token(room_number):
    # Create a JWT token with room number and expiration
    payload = {
        'room': room_number,
        'exp': datetime.now() + timedelta(hours=24)  # Token expires in 24 hours
    }
    print(f"Generating token for room {room_number}: exp={payload['exp']} now={datetime.now()}")
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def create_qr_with_design(room_number, qr_url):
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    # Create QR code image
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # Create a new image with white background
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to load a font
        title_font = ImageFont.truetype(FONT_PATH, 42)
        subtitle_font = ImageFont.truetype(FONT_PATH, 32)
        text_font = ImageFont.truetype(FONT_PATH, 24)
    except IOError:
        # Fallback to default font if specified font is not found
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Add lodge logo if exists
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH)
            logo.thumbnail((250, 250))  # Logo size
            logo_y = 40  # Vertical position
            logo_x = width//2 - 110  # Adjusted to be more centered (was -100)
            img.paste(logo, (logo_x, logo_y))  # Position logo
        except Exception as e:
            print(f"Error loading logo: {e}")
    
    # Position QR code with increased gap from logo
    qr_size = 480  # Increased from 400 for better scannability
    qr_img = qr_img.resize((qr_size, qr_size))
    qr_y = 350  # Increased from 280 to add more space below logo
    qr_position = ((width - qr_size) // 2, qr_y)
    
    # Paste QR code
    img.paste(qr_img, qr_position)
    
    # Define fonts - using system fonts for consistency
    try:
        # Try loading Arial for clean, modern look
        title_font = ImageFont.truetype("arial.ttf", 32)  # Slightly larger
        room_font = ImageFont.truetype("arialbd.ttf", 46)  # Slightly larger and bold for room number
    except IOError:
        # Fallback to default font if needed
        title_font = ImageFont.load_default()
        room_font = ImageFont.load_default()
    
    # Add scan instruction with better spacing
    scan_text = "SCAN TO ORDER FOOD"
    text_width = title_font.getlength(scan_text)
    
    # Calculate positions for better visual balance
    text_y = qr_y + qr_size + 50  # 50px below QR code (increased from 40px)
    
    # Draw text with better spacing
    draw.text((width//2, text_y), scan_text,
             fill="red", font=title_font, anchor="mm")
    
    # Add room number with better spacing
    room_text = f"ROOM {room_number}"
    room_y = text_y + 60  # 60px below scan text
    draw.text((width//2, room_y), room_text,
             fill="red", font=room_font, anchor="mm")
    
    # Add a subtle decorative line above the room number
    line_y = room_y - 40  # 20px above room number
    draw.line([(width//2 - 100, line_y), (width//2 + 100, line_y)], 
             fill="red", width=2)
    
    return img

# Generate QR codes for rooms 101-121
room_numbers = range(101, 122)

# Create output directory if it doesn't exist
output_dir = "qr_codes"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

for room in room_numbers:
    # Generate secure token for the room
    token = generate_room_token(str(room))
    qr_url = f"{BASE_URL}{token}"
    
    # Create QR code with design
    qr_img = create_qr_with_design(room, qr_url)
    
    # Save the image
    output_path = os.path.join(output_dir, f"room_{room}_qr.png")
    qr_img.save(output_path)
    print(f"Generated QR code for Room {room}: {output_path}")

print("\nAll QR codes generated successfully in the 'qr_codes' directory.")
print("You can now print these QR codes and place them in the respective rooms.")