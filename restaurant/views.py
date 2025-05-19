from django.views.decorators.csrf import csrf_protect 
from django.views.decorators.csrf import csrf_exempt 
from django.shortcuts import render,redirect
from .forms import ProfileImageForm
from django.http import JsonResponse, HttpResponse
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from restaurant.models import Food, Category, Room, RoomOrder, RoomOrderItem, Cart, CartItem, RoomCategory
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import WebsiteVisit, DashboardStats, Profile, PasswordResetOTP, SignupOTP
import json
import logging
from django.views.decorators.http import require_GET
from django.utils import timezone
import jwt
from datetime import datetime, timedelta
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import random
from django.core.mail import send_mail
from django.contrib import messages



# Home Page
def index(request):
    if request.user.is_authenticated:
        Profile.objects.get_or_create(user=request.user)
    stats = DashboardStats.objects.first()
    return render(request, 'index.html', {'stats': stats})

# Signup Page
@csrf_protect
def signup_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        email = request.POST.get('email')
        gender = request.POST.get('gender')
        
        # Basic validation
        if not username or not password or not password2 or not email:
            messages.error(request, 'All fields are required.')
            return render(request, 'signup.html', request.POST)
        elif password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'signup.html', request.POST)
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'signup.html', request.POST)
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'signup.html', request.POST)
        elif SignupOTP.objects.filter(username=username).exists():
             messages.error(request, 'A signup attempt with this username is already in progress. Please check your email for the verification OTP.')
             return render(request, 'signup.html', request.POST)
        elif SignupOTP.objects.filter(email=email).exists():
             messages.error(request, 'A signup attempt with this email address is already in progress. Please check your email for the verification OTP.')
             return render(request, 'signup.html', request.POST)
        elif SignupOTP.objects.filter(email=email, is_used=False).exists():
             messages.error(request, 'An OTP has already been sent to this email. Please check your inbox or try again later.')
             
        # Generate and save OTP along with user details temporarily
        otp = generate_otp()
        SignupOTP.objects.create(
            email=email,
            username=username,
            temp_password=password, # Storing plaintext temporarily before hashing during user creation
            otp=otp,
            gender=gender
        )
        
        # Send email with OTP
        send_mail(
            'Verify Your Email Address - QR Chef',
            f'Your OTP for email verification is: {otp}\n\nThis OTP is valid for 10 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        messages.success(request, 'Please check your email for the verification OTP.') # Message updated
        
        # Redirect to OTP verification page, passing email in session
        request.session['signup_email_for_otp'] = email
        return redirect('signup_otp_verify')

    return render(request, 'signup.html')

def signup_otp_verify(request):
    if 'signup_email_for_otp' not in request.session:
        messages.error(request, 'Please sign up first to get an OTP.')
        return redirect('signup')
        
    email = request.session['signup_email_for_otp']

    if request.method == 'POST':
        otp = request.POST.get('otp')
        try:
            otp_obj = SignupOTP.objects.filter(
                email=email,
                otp=otp,
                is_used=False
            ).latest('created_at')
            
            if otp_obj.is_valid():
                # Create the actual user account
                user = User.objects.create_user(
                    username=otp_obj.username,
                    email=otp_obj.email,
                    password=otp_obj.temp_password, # Use the temporarily stored password
                    is_active=True # User is active upon verification
                )
                user.save()
                
                # Transfer gender from SignupOTP to Profile
                profile, created = Profile.objects.get_or_create(user=user)
                profile.gender = otp_obj.gender
                profile.save()
                
                # Mark OTP as used and potentially delete the SignupOTP object
                otp_obj.is_used = True
                otp_obj.save()
                # Optional: Delete the OTP record after successful verification
                otp_obj.delete()
                
                # Clear the email from session
                del request.session['signup_email_for_otp']
                
                messages.success(request, 'Email verified successfully! Your account is now active. You can now log in.') # Message updated
                return redirect('login')
            else:
                messages.error(request, 'OTP has expired or is invalid.')
                # Delete the failed OTP attempt and clear session
                otp_obj.delete()
                del request.session['signup_email_for_otp']
                return redirect('signup') # Redirect back to signup page
        except SignupOTP.DoesNotExist:
            messages.error(request, 'Invalid OTP or email.')
            # Clear session for security if email doesn't match any pending OTP
            if 'signup_email_for_otp' in request.session:
                del request.session['signup_email_for_otp']
            return redirect('signup') # Redirect back to signup page
            
    return render(request, 'signup_otp_verify.html', {'email': email}) # Pass email to the template

# Logout Page
def logout_view(request):
    logout(request)
    return redirect('login')

# Profile Page
def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileImageForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile photo updated successfully!')
    # Always redirect to home after POST or GET; modal handles display
    return redirect('index')

# Login Page
from django.middleware.csrf import get_token

def login_page(request):
    if request.method == 'POST':
        print("CSRF cookie:", request.COOKIES.get('csrftoken'))
        print("CSRF POST:", request.POST.get('csrfmiddlewaretoken'))
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if the user is active
            if user.is_active:
                login(request, user)
                # Robust: always ensure profile exists
                Profile.objects.get_or_create(user=user)
                return redirect('index')
            else:
                messages.error(request, 'Please verify your email address before logging in.')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

# Room Page
def room(request):
    rooms = Room.objects.all()
    return render(request, 'room.html', {'rooms': rooms})

# About Us Page
def aboutus(request):
    return render(request, 'aboutus.html')

# Menu Page
logger = logging.getLogger(__name__)
def menu_view(request):
    print('[DEBUG] menu_view session:', dict(request.session))
    # 1. Capture room number from URL if present
    room_no = request.GET.get('room')
    if room_no:
        request.session['room_no'] = room_no

    print('[DEBUG] menu_view session room_no:', request.session.get('room_no'))

    categories = Category.objects.all()
    category_id = request.GET.get('category')
    if category_id:
        food_items = Food.objects.filter(category_id=category_id)
        categories = categories.filter(id=category_id)
    else:
        food_items = Food.objects.all()

    # Attach items to each category
    for category in categories:
        category.items = food_items.filter(category=category)
    
    # Get cart items if user is authenticated
    cart_items = []
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_items = CartItem.objects.filter(cart=cart)

    context = {
        'categories': categories,
        'food_items': food_items,
        'cart_items': cart_items,
    }
    return render(request, 'menu.html', context)

# API to fetch cart data
def get_cart(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)
    
    cart_data = {
        "items": [
            {
                "id": item.food.id,
                "name": item.food.name,
                "price": float(item.food.price),
                "quantity": item.quantity,
                "total": float(item.get_total_price())
            }
            for item in cart_items
        ],
        "total_price": float(cart.get_total_price())
    }
    
    return JsonResponse({"cart": cart_data})

# Update Cart (Add items or update quantities)
def update_cart(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            cart, created = Cart.objects.get_or_create(user=request.user)
            food_id = data.get("id")
            quantity = data.get("quantity", 1)

            try:
                food = Food.objects.get(id=food_id)
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    food=food,
                    defaults={"quantity": quantity}
                )
                if not created:
                    cart_item.quantity += quantity
                    cart_item.save()

                return JsonResponse({
                    "success": True,
                    "message": "Item added to cart",
                    "cart": {
                        "items": [
                            {
                                "id": item.food.id,
                                "name": item.food.name,
                                "price": float(item.food.price),
                                "quantity": item.quantity,
                                "total": float(item.get_total_price())
                            }
                            for item in cart.cartitem_set.all()
                        ],
                        "total_price": float(cart.get_total_price())
                    }
                })
            except Food.DoesNotExist:
                return JsonResponse({"success": False, "error": "Food item not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid request"})

# Add Food Item to Cart
def add_to_cart(request, food_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    try:
        food = Food.objects.get(id=food_id)
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            food=food,
            defaults={"quantity": 1}
        )
        if not created:
            cart_item.quantity += 1
            cart_item.save()

        return JsonResponse({
            "success": True,
            "message": "Item added to cart",
            "cart": {
                "items": [
                    {
                        "id": item.food.id,
                        "name": item.food.name,
                        "price": float(item.food.price),
                        "quantity": item.quantity,
                        "total": float(item.get_total_price())
                    }
                    for item in cart.cartitem_set.all()
                ],
                "total_price": float(cart.get_total_price())
            }
        })
    except Food.DoesNotExist:
        return JsonResponse({"success": False, "error": "Food item not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

# View Cart
@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)
    
    # Get room number from session if available
    room_no = request.session.get('room_no')
    room_category = None
    if room_no:
        # Find the room category that contains this room number
        for category in RoomCategory.objects.all():
            if room_no in category.get_room_numbers_list():
                room_category = category
                break
    
    context = {
        'cart_items': cart_items,
        'total': cart.get_total_price(),
        'room_no': room_no,
        'room_category': room_category,
    }
    return render(request, 'cart.html', context)

@csrf_exempt
def remove_from_cart(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            
            cart = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.get(id=item_id, cart=cart)
            cart_item.delete()
            
            return JsonResponse({
                "success": True,
                "cart": {
                    "items": [
                        {
                            "id": item.food.id,
                            "name": item.food.name,
                            "price": float(item.food.price),
                            "quantity": item.quantity,
                            "total": float(item.get_total_price())
                        }
                        for item in cart.cartitem_set.all()
                    ],
                    "total_price": float(cart.get_total_price())
                }
            })
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)

# Order placement is now handled by confirm_order, which supports AJAX, room number, payment method, and both authenticated/anonymous users.
# The old place_order view has been removed for clarity and to prevent duplicates.

logger = logging.getLogger(__name__)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def confirm_order(request):
    if request.method == 'POST':
        # Check if room_no is in session (from QR code scan)
        room_no_session = request.session.get('room_no')
        if not room_no_session:
            return JsonResponse({"success": False, "error": "Please scan the QR code in your room to confirm the order."}, status=400)

        try:
            data = json.loads(request.body)
            # Ensure the room_no from the request body matches the session (optional, but good practice)
            room_no_data = data.get('room_no')
            if not room_no_data or room_no_data != room_no_session:
                 return JsonResponse({"success": False, "error": "Invalid room number or session mismatch. Please rescan the QR code."}, status=400)

            room_no = room_no_data # Use the room number from the data after validation
            items = data.get('items', [])
            
            # Original check for room_no in data (can keep for redundancy or remove)
            # if not room_no:
            #     return JsonResponse({"success": False, "error": "Room number is required"}, status=400)
            
            if not items:
                return JsonResponse({"success": False, "error": "Cart is empty"}, status=400)
            
            # Validate room number
            room_category = None
            for category in RoomCategory.objects.all():
                if room_no in category.get_room_numbers_list():
                    room_category = category
                    break
            
            if not room_category:
                return JsonResponse({"success": False, "error": "Invalid room number"}, status=400)
            
            # Try to get an active room order for this room and category
            room_order = RoomOrder.objects.filter(
                room_number=room_no,
                category=room_category,
                is_active=True
            ).first()

            if not room_order:
                room_order = RoomOrder.objects.create(
                    room_number=room_no,
                    category=room_category,
                    is_active=True,
                    check_in=timezone.now()
                )
            
            # Add or update room order items
            for item in items:
                try:
                    food = Food.objects.get(id=item['id'])
                    order_item, created = RoomOrderItem.objects.get_or_create(
                        room_order=room_order,
                        food=food,
                        defaults={'quantity': item['quantity'], 'price': food.price}
                    )
                    if not created:
                        order_item.quantity += item['quantity']
                        order_item.save()
                except Food.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Food item {item['id']} not found"}, status=400)
            
            return JsonResponse({
                "success": True,
                "message": "Order confirmed successfully",
                "order_id": room_order.id,
                "room_number": room_order.room_number,
                "total_bill": float(room_order.get_total_bill())
            })
            
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)

def website_visits(request):
    visit = WebsiteVisit.objects.first()
    if visit:
        if visit.count < 0:
            visit.count = 0
        visit.count += 1
        visit.save()
    return JsonResponse({'visits': visit.count if visit else 0})

@require_GET
def get_category_by_room_number(request):
    room_number = request.GET.get('room_number')
    if not room_number:
        return JsonResponse({'error': 'Room number is required'}, status=400)
    
    for category in RoomCategory.objects.all():
        if room_number in category.get_room_numbers_list():
            return JsonResponse({
                'category_id': category.id,
                'category_name': category.name,
                'price_per_night': float(category.price_per_night)
            })
    
    return JsonResponse({'error': 'Room not found'}, status=404)

@require_http_methods(["GET"])
def room_access(request, token):
    try:
        # Decode and verify the JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        room_number = payload.get('room')
        
        # Check if token is expired
        exp = payload.get('exp')
        if datetime.now().timestamp() > exp:
            return JsonResponse({
                'error': 'Access token has expired. Please scan the QR code again.'
            }, status=401)
        
        # Validate room number exists
        room_category = None
        for category in RoomCategory.objects.all():
            if room_number in category.get_room_numbers_list():
                room_category = category
                break
        
        if not room_category:
            return JsonResponse({
                'error': 'Invalid room number'
            }, status=400)
        
        # Store room number in session with expiration
        request.session['room_no'] = room_number
        request.session['room_access_time'] = datetime.now().timestamp()
        request.session.modified = True  # Force session save
        print("[DEBUG] Session set:", request.session['room_no'], request.session['room_access_time'])
        request.session.save()  # Explicitly save session before redirect
        # Redirect to menu page
        return redirect('menu')
        
    except jwt.InvalidTokenError:
        return JsonResponse({
            'error': 'Invalid access token'
        }, status=401)
    except Exception as e:
        print("[DEBUG] Exception in room_access:", str(e))
        return JsonResponse({
            'error': str(e)
        }, status=500)   

@user_passes_test(lambda u: u.is_staff)
def analytics_view(request):
    from_date_str = request.POST.get('from_date')
    to_date_str = request.POST.get('to_date')
    payment_method = request.POST.get('payment_method', '') # Default to '' for 'All'

    orders = None
    total_revenue = 0

    payment_method_choices = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Mobile', 'Mobile'),
        ('Online', 'Online'),
        # Add other payment methods as needed
    ]

    if request.method == 'POST':
        # (Date parsing and filtering logic)
        try:
            if from_date_str:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            else:
                from_date = None

            if to_date_str:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            else:
                to_date = None

            # Start with all RoomOrder objects
            queryset = RoomOrder.objects.all()

            # Filter by date range if dates are provided
            if from_date:
                queryset = queryset.filter(check_in__date__gte=from_date)
            if to_date:
                # Add one day to the to_date so that the filter is inclusive of the selected end date
                queryset = queryset.filter(check_in__date__lte=to_date)

            # Filter by payment method if a specific one is selected
            if payment_method:
                queryset = queryset.filter(payment_method=payment_method)

            orders = queryset

            # Calculate total revenue
            total_revenue = sum(order.get_total_bill() for order in orders)

        except ValueError:
            # Handle invalid date format
            orders = [] # Or None, depending on desired behavior
            total_revenue = 0
            # Optionally, add an error message
            # messages.error(request, "Invalid date format.")


    context = {
        'from_date': from_date_str,
        'to_date': to_date_str,
        'payment_method': payment_method,
        'payment_method_choices': payment_method_choices,
        'orders': orders,
        'total_revenue': total_revenue,
        'request_path': request.path, # Add the request path to context
    }

    return render(request, 'admin/restaurant/roomorder/analytics.html', context)

@user_passes_test(lambda u: u.is_staff)
def generate_sales_report_pdf(request, from_date=None, to_date=None, payment_method=None):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"' # Added timestamp for unique filenames

    # Create the PDF object
    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Retrieve date and payment method from GET parameters
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')
    payment_method = request.GET.get('payment_method', None)

    # --- Add Lodge Header Information ---
    from reportlab.lib.utils import ImageReader
    from django.conf import settings
    import os

    # Construct the absolute path to the logo
    logo_path = os.path.join(settings.STATICFILES_DIRS[0], 'images', 'qr.png')

    # Check if logo file exists before adding
    if os.path.exists(logo_path):
        try:
            # Adjust width as needed, height will scale proportionally
            logo = Image(logo_path, width=1.2*inch, height=1.2*inch)
        except Exception as e:
             # Handle cases where ImageReader might fail
             logo = Paragraph(f"[Logo Error: {e}]", styles['Normal'])
    else:
        logo = Paragraph("[Logo not found]", styles['Normal'])

    # Lodge Information Paragraphs
    # Create a specific style for lodge info with reduced spacing and right alignment
    lodge_info_style = ParagraphStyle(
        'LodgeInfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=5, # Increased space after each line
        alignment=2, # Right alignment
    )

    lodge_name = Paragraph("<font size=16><b>Bhanjyang Village and Lodge</b></font>", lodge_info_style) # Increased font size
    # Add extra space after this paragraph
    lodge_name.spaceAfter = 10 # You can adjust this value as needed
    lodge_address = Paragraph("<font size=10>Sarankot, Pokhara</font>", lodge_info_style) # Use new style
    lodge_contact = Paragraph("<font size=10>Contact No: +977-9846852692</font>", lodge_info_style) # Use new style

    # Create a table for the header to align logo and info
    header_data = [[logo, [lodge_name, lodge_address, lodge_contact]]]
    # Adjusted column widths slightly to give more space to text if needed
    header_table = Table(header_data, colWidths=[1.5*inch, doc.width - 1.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'), # Align logo to top
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'), # Align info to RIGHT
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.5*inch)) # Increased space after header
    # --- End Lodge Header Information ---

    # Add main title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18, # Slightly smaller for better integration with header
        spaceAfter=14,
        alignment=1 # Center align
    )
    elements.append(Paragraph("Sales Report", title_style))

    # Add date range and payment method
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=15,
        alignment=1
    )
    # Display the actual dates if available, otherwise show 'None'
    display_from_date = from_date_str if from_date_str else 'None'
    display_to_date = to_date_str if to_date_str else 'None'
    date_text = f"Period: {display_from_date} to {display_to_date}"
    if payment_method:
        date_text += f" (Payment Method: {dict(RoomOrder.PAYMENT_METHOD_CHOICES).get(payment_method, payment_method)})"
    elements.append(Paragraph(date_text, date_style))
    elements.append(Spacer(1, 0.2*inch))

    # Get orders data and build report elements
    try:
        # Parse date strings only if they exist
        from_datetime = datetime.strptime(from_date_str, '%Y-%m-%d') if from_date_str else None
        # Add one day to the to_date so that the filter is inclusive of the selected end date, only if to_date_str exists
        # Need to handle None for to_date_str before adding timedelta
        to_datetime = datetime.strptime(to_date_str, '%Y-%m-%d') + timedelta(days=1) if to_date_str else None

        # Start with all RoomOrder objects
        queryset = RoomOrder.objects.all()

        # Filter by date range if dates are provided
        if from_datetime:
            queryset = queryset.filter(check_in__date__gte=from_datetime.date()) # Filter by date part only
        if to_datetime:
             # Filter by date part only for check_in less than the day AFTER to_date
             queryset = queryset.filter(check_in__date__lt=to_datetime.date()) 

        # Filter by payment method if a specific one is selected
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        orders = queryset.order_by('check_in') # Order by check-in date

        if orders:
            # Create table data for the main report table
            data = [['Room No.', 'Customer Name', 'Amount', 'Date']]
            
            for order in orders:
                data.append([
                    str(order.room_number) if order.room_number else 'N/A',
                    order.customer_name or 'N/A',
                    f"Rs {order.get_total_bill():.2f}",
                    order.check_in.strftime('%Y-%m-%d') if order.check_in else 'N/A', # Using check-in date as the order date
                ])

            # Create the main report table
            # Adjusted column widths for better spacing
            col_widths = [doc.width*0.15, doc.width*0.4, doc.width*0.2, doc.width*0.25]
            table = Table(data, colWidths=col_widths)

            # Style for the main report table - Enhanced Styling
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#417690')), # Django Admin Blue Header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10), # Slightly smaller font for table
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white), # White background for rows
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ddd')), # Light grey grid lines
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#ddd')), # Light grey border around table
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'), # Left align Room No.
                ('ALIGN', (1, 1), (1, -1), 'LEFT'), # Left align Customer Name
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'), # Right align Amount
                ('ALIGN', (3, 1), (3, -1), 'CENTER'), # Center align Date
                ('FONTSIZE', (0, 1), (-1, -1), 9), # Font size for table data
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

            ]))

            elements.append(table)

            # Add overall summary (Total Revenue) - Enhanced Styling
            total_revenue = sum(order.get_total_bill() for order in orders)
            
            # Summary style for Total Revenue
            total_revenue_style = ParagraphStyle(
                'TotalRevenueStyle',
                parent=styles['Heading2'], 
                spaceBefore=15,
                alignment=2, # Right align summary
                fontSize=12,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#333') # Dark grey color

            )
            
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"Total Revenue: Rs {total_revenue:.2f}", total_revenue_style))

        else:
            elements.append(Paragraph("No orders found for the selected date range and payment method.", styles['Normal']))

    except Exception as e:
        elements.append(Paragraph(f"Error generating report: {str(e)}", styles['Normal']))

    # Build PDF
    doc.build(elements)
    return response   

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

@csrf_protect
def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate OTP
            otp = generate_otp()
            # Save OTP
            PasswordResetOTP.objects.create(user=user, otp=otp)
            # Send email with OTP
            send_mail(
                'Password Reset OTP - QR Chef',
                f'Your OTP for password reset is: {otp}\n\nThis OTP is valid for 10 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return redirect('password_reset_otp_verify')
        except User.DoesNotExist:
            messages.error(request, 'No user found with this email address.')
    return render(request, 'password_reset.html')

def password_reset_otp_verify(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp = request.POST.get('otp')
        try:
            user = User.objects.get(email=email)
            otp_obj = PasswordResetOTP.objects.filter(
                user=user,
                otp=otp,
                is_used=False
            ).latest('created_at')
            
            if otp_obj.is_valid():
                # Mark OTP as used
                otp_obj.is_used = True
                otp_obj.save()
                # Store user email in session for password reset
                request.session['reset_email'] = email
                return redirect('password_reset_confirm')
            else:
                messages.error(request, 'OTP has expired or is invalid.')
        except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
            messages.error(request, 'Invalid OTP or email.')
    return render(request, 'password_reset_otp_verify.html')

def password_reset_confirm(request):
    if 'reset_email' not in request.session:
        return redirect('password_reset')
        
    if request.method == 'POST':
        email = request.session['reset_email']
        password1 = request.POST.get('new_password1')
        password2 = request.POST.get('new_password2')
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'password_reset_confirm.html')
            
        try:
            user = User.objects.get(email=email)
            user.set_password(password1)
            user.save()
            del request.session['reset_email']
            messages.success(request, 'Password has been reset successfully.')
            return redirect('login')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('password_reset')
            
    return render(request, 'password_reset_confirm.html')   