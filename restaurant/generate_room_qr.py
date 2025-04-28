import qrcode

BASE_URL = "http://192.168.110.49:8000/menu/?room="  # Change to your production URL if needed

room_numbers = range(101, 111)  # Example: Rooms 101 to 110

for room in room_numbers:
    qr_url = f"{BASE_URL}{room}"
    img = qrcode.make(qr_url)
    img.save(f"room_{room}.png")
    print(f"Generated QR for Room {room}: {qr_url}")