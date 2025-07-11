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
from django.db.models import Q, Count, Sum, F, Avg, ExpressionWrapper
from django.db.models.functions import ExtractMonth, ExtractYear, Coalesce
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
import random
from django.core.mail import send_mail
from django.contrib import messages
from reportlab.platypus import PageTemplate, BaseDocTemplate, Frame
from decimal import Decimal

# Define custom ReportLab templates at the top level
from reportlab.platypus import PageTemplate, BaseDocTemplate, Frame

class NumberedPageTemplate(PageTemplate):
    def __init__(self, template_id, pagesize):
        frame = Frame(0, 0, pagesize[0], pagesize[1], id='normal')
        PageTemplate.__init__(self, template_id, [frame])
        
    def beforeDrawPage(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(cm, 0.75 * cm, f"Page {doc.page}")
        canvas.restoreState()

# Create a custom document template
class NumberedDocTemplate(BaseDocTemplate):
    def __init__(self, filename, pagesize, **kw):
        BaseDocTemplate.__init__(self, filename, pagesize=pagesize, **kw)
        # Define a frame with margins and a border
        margin = 1.5 * cm  # Adjust margin as needed
        # Subtracting twice the margin from page width and height for frame dimensions
        frame_width = pagesize[0] - 2 * margin
        frame_height = pagesize[1] - 2 * margin
        # Origin of the frame (bottom-left corner)
        frame_x = margin
        frame_y = margin

        # Create a frame with a border
        frame = Frame(frame_x, frame_y, frame_width, frame_height,
                      leftPadding=20, bottomPadding=20,
                      rightPadding=20, topPadding=20) # Increase padding around the frame


        template = PageTemplate(id='numbered_page', frames=[frame], onPage=self.draw_page_border)
        self.addPageTemplates(template)
        
    def draw_page_border(self, canvas, doc):
        canvas.saveState()
        margin = 1.5 * cm
        # Draw page number only, no border
        canvas.setFont('Helvetica', 9)
        # Position page number relative to the bottom margin
        canvas.drawString(margin, 0.75 * cm, f"Page {doc.page}")
        canvas.restoreState()

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
    # Get date parameters from either GET or POST
    from_date_str = request.GET.get('from_date') or request.POST.get('from_date')
    to_date_str = request.GET.get('to_date') or request.POST.get('to_date')
    payment_method = request.GET.get('payment_method') or request.POST.get('payment_method', '')

    orders = None
    total_revenue = 0
    room_occupancy_data = None
    food_sales_data = None
    monthly_revenue_data = None

    payment_method_choices = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Mobile', 'Mobile'),
        ('Online', 'Online'),
    ]

    # Start with all RoomOrder objects
    queryset = RoomOrder.objects.all()

    # Process date filters if provided
    if from_date_str and to_date_str:
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()

            # Filter by date range
            queryset = queryset.filter(
                check_in__date__gte=from_date,
                check_in__date__lte=to_date
            )

            # Filter by payment method if specified
            if payment_method:
                queryset = queryset.filter(payment_method=payment_method)

            orders = queryset.order_by('check_in')

            # Fetch related RoomOrderItems for each order
            for order in orders: # This is for the table view, not strictly needed for charts but kept for existing functionality
                order.items = order.roomorderitem_set.all()

            # Calculate total revenue (for the table view)
            total_revenue = sum(order.get_total_bill() for order in orders)

            # --- Data for Charts ---

            # 1. Room Occupancy Pie Chart (based on filtered orders)
            # Track rooms and days stayed per category
            room_occupancy_data = {}
            for order in orders:
                if not order.category or not order.room_number:
                    continue
                
                cat_name = order.category.name
                room_num = order.room_number.strip()
                days = order.get_days_stayed() or 1
                
                if cat_name not in room_occupancy_data:
                    room_occupancy_data[cat_name] = {
                        'rooms': {},
                        'total_days': 0
                    }
                
                # Track days per room
                if room_num not in room_occupancy_data[cat_name]['rooms']:
                    room_occupancy_data[cat_name]['rooms'][room_num] = 0
                room_occupancy_data[cat_name]['rooms'][room_num] += days
                room_occupancy_data[cat_name]['total_days'] += days
            
            # Convert to list of dicts for template
            room_occupancy_list = []
            for cat, data in room_occupancy_data.items():
                room_details = []
                for room_num, days in data['rooms'].items():
                    room_details.append(f"{room_num} - {days} day{'s' if days > 1 else ''}")
                
                room_occupancy_list.append({
                    'category__name': cat,
                    'room_count': len(data['rooms']),
                    'rooms': ", ".join(room_details),
                    'total_days': data['total_days']
                })
            
            # Keep labels simple for the legend
            room_occupancy_labels = [item['category__name'] for item in room_occupancy_list]
            room_occupancy_counts = [item['room_count'] for item in room_occupancy_list]
            
            # Add room details to the context for tooltips
            room_occupancy_details = {
                item['category__name']: {
                    'rooms': item['rooms'],
                    'total_days': item['total_days']
                }
                for item in room_occupancy_list
            }

            # 2. Food Sold by Category Pie Chart (based on items in filtered orders)
            # Get items from the filtered orders
            filtered_order_item_ids = [item.id for order in orders for item in order.roomorderitem_set.all()]
            food_sales_data = RoomOrderItem.objects.filter(id__in=filtered_order_item_ids).values('food__category__name').annotate(total_quantity=Sum('quantity'))

            food_sales_labels = [item['food__category__name'] or 'Uncategorized' for item in food_sales_data]
            food_sales_quantities = [item['total_quantity'] for item in food_sales_data]

            # 3. Monthly Sales Revenue Bar Chart (based on filtered orders)
            # Group by month and year within the selected date range
            from collections import defaultdict
            from decimal import Decimal
            
            # Initialize a dictionary to store monthly data
            monthly_data = defaultdict(lambda: {
                'food_revenue': Decimal('0.00'),
                'room_revenue': Decimal('0.00'),
                'total_revenue': Decimal('0.00')
            })
            
            # Process each order and group by month
            for order in orders:
                month = order.check_in.month
                year = order.check_in.year
                month_key = f"{year}-{month:02d}"
                
                # Calculate food revenue for this order
                food_revenue = sum(
                    item.quantity * item.price 
                    for item in order.roomorderitem_set.all()
                )
                
                # Calculate room revenue for this order
                room_revenue = Decimal('0.00')
                if order.category and order.category.price_per_night:
                    room_revenue = order.category.price_per_night * order.get_days_stayed()
                
                # Update monthly data
                monthly_data[month_key]['year'] = year
                monthly_data[month_key]['month'] = month
                monthly_data[month_key]['food_revenue'] += food_revenue
                monthly_data[month_key]['room_revenue'] += room_revenue
                monthly_data[month_key]['total_revenue'] += (food_revenue + room_revenue)
            
            # Convert to list format expected by the template
            monthly_revenue_data = [
                {
                    'year': data['year'],
                    'month': data['month'],
                    'food_revenue': data['food_revenue'],
                    'room_revenue': data['room_revenue'],
                    'total_revenue': data['total_revenue']
                }
                for data in monthly_data.values()
            ]
            
            # Sort by year and month
            monthly_revenue_data.sort(key=lambda x: (x['year'], x['month']))
            
            # Format data for Chart.js
            monthly_revenue_labels = [f"{item['year']}-{item['month']:02d}" for item in monthly_revenue_data]
            monthly_food_revenue = [float(item['food_revenue']) for item in monthly_revenue_data]
            monthly_room_revenue = [float(item['room_revenue']) for item in monthly_revenue_data]
            monthly_revenue_values = [f + r for f, r in zip(monthly_food_revenue, monthly_room_revenue)]

        except ValueError:
            # Handle invalid date format
            orders = [] # Or None, depending on desired behavior
            total_revenue = 0
            room_occupancy_labels = []
            room_occupancy_counts = []
            food_sales_labels = []
            food_sales_quantities = []
            monthly_revenue_labels = []
            monthly_revenue_values = []
            # Optionally, add an error message
            # messages.error(request, "Invalid date format.")

    else: # For GET requests, initialize with empty data or data for all time
         orders = queryset.order_by('check_in')
         for order in orders:
            order.items = order.roomorderitem_set.all()
         total_revenue = sum(order.get_total_bill() for order in orders)

         # Calculate data for all time for GET request initial load
         room_occupancy_data = {}
         for order in RoomOrder.objects.all():
             if not order.category or not order.room_number:
                 continue
             
             cat_name = order.category.name
             room_num = order.room_number.strip()
             days = order.get_days_stayed() or 1
             
             if cat_name not in room_occupancy_data:
                 room_occupancy_data[cat_name] = {
                     'rooms': {},
                     'total_days': 0
                 }
             
             # Track days per room
             if room_num not in room_occupancy_data[cat_name]['rooms']:
                 room_occupancy_data[cat_name]['rooms'][room_num] = 0
             room_occupancy_data[cat_name]['rooms'][room_num] += days
             room_occupancy_data[cat_name]['total_days'] += days
         
         # Convert to list of dicts for template
         room_occupancy_list = []
         for cat, data in room_occupancy_data.items():
             room_details = []
             for room_num, days in data['rooms'].items():
                 room_details.append(f"{room_num} - {days} day{'s' if days > 1 else ''}")
             
             room_occupancy_list.append({
                 'category__name': cat,
                 'room_count': len(data['rooms']),
                 'rooms': ", ".join(room_details),
                 'total_days': data['total_days']
             })
         
         # Keep labels simple for the legend
         room_occupancy_labels = [item['category__name'] for item in room_occupancy_list]
         room_occupancy_counts = [item['room_count'] for item in room_occupancy_list]
         
         # Add room details to the context for tooltips
         room_occupancy_details = {
             item['category__name']: {
                 'rooms': item['rooms'],
                 'total_days': item['total_days']
             }
             for item in room_occupancy_list
         }

         food_sales_data = RoomOrderItem.objects.all().values('food__category__name').annotate(total_quantity=Sum('quantity'))
         food_sales_labels = [item['food__category__name'] or 'Uncategorized' for item in food_sales_data]
         food_sales_quantities = [item['total_quantity'] for item in food_sales_data]

         monthly_revenue_data = RoomOrder.objects.annotate(
             month=ExtractMonth('check_in'), 
             year=ExtractYear('check_in')
             ).values('year', 'month').annotate(
                 monthly_sum=Sum(models.F('roomorderitem__quantity') * models.F('roomorderitem__price'), output_field=models.DecimalField())
                 ).order_by('year', 'month')
         monthly_revenue_labels = [f"{item['year']}-{item['month']:02d}" for item in monthly_revenue_data]
         monthly_revenue_values = [float(item['monthly_sum']) if item['monthly_sum'] is not None else 0 for item in monthly_revenue_data]


    return render(request, 'admin/restaurant/roomorder/analytics.html', {
        'orders': orders,
        'total_revenue': total_revenue,
        'room_occupancy_labels': json.dumps(room_occupancy_labels) if room_occupancy_data else '[]',
        'room_occupancy_counts': json.dumps(room_occupancy_counts) if room_occupancy_data else '[]',
        'room_occupancy_details': json.dumps(room_occupancy_details) if room_occupancy_data else '{}',
        'food_sales_labels': json.dumps(food_sales_labels) if food_sales_data else '[]',
        'food_sales_quantities': json.dumps(food_sales_quantities) if food_sales_data else '[]',
        'monthly_revenue_labels': json.dumps(monthly_revenue_labels) if 'monthly_revenue_labels' in locals() else '[]',
        'monthly_revenue_values': json.dumps(monthly_revenue_values) if 'monthly_revenue_values' in locals() else '[]',
        'monthly_food_revenue': json.dumps(monthly_food_revenue) if 'monthly_food_revenue' in locals() else '[]',
        'monthly_room_revenue': json.dumps(monthly_room_revenue) if 'monthly_room_revenue' in locals() else '[]',
        'payment_method_choices': payment_method_choices,
        'selected_payment_method': payment_method,
        'from_date': from_date_str,
        'to_date': to_date_str,
        'request_path': request.path,
    })

@user_passes_test(lambda u: u.is_staff)
def generate_sales_report_pdf(request, from_date=None, to_date=None, payment_method=None):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    response['Content-Disposition'] = f'attachment; filename="sales_report_{timestamp}.pdf"'

    # Create the PDF object using the custom template
    doc = NumberedDocTemplate(response, pagesize=letter) # Create doc object here
    print(f"Debug: NumberedDocTemplate instantiated successfully: {doc}") # Keep debug print

    # Create the PDF object
    # doc = SimpleDocTemplate(response, pagesize=letter)
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
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), # Center align all content in the header table
        ('BACKGROUND', (0, 0), (1, 0), colors.white), # White background
        ('TEXTCOLOR', (1, 0), (1, 0), colors.black), # Black text for lodge info on white background
        ('BOTTOMPADDING', (0, 0), (1, 0), 15), # Increased bottom padding
        ('TOPPADDING', (0, 0), (1, 0), 15), # Increased top padding
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white), # Remove inner grid lines
        ('BOX', (0, 0), (-1, -1), 0, colors.white), # Remove box border around table data
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch)) # Slightly reduced space after header
    # --- End Lodge Header Information ---

    # Add main title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16, # Adjusted font size
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

        # Fetch related RoomOrderItems for each order
        for order in orders:
            order.items = order.roomorderitem_set.all()

        if orders:
            # Create a style for order details
            order_details_style = ParagraphStyle(
                'OrderDetailsStyle',
                parent=styles['Normal'],
                spaceAfter=6,
                fontSize=10,
                fontName='Helvetica-Bold',
                # Remove individual border, rely on main page border
                borderWidth=0,
                borderColor=None,
                borderPadding=0,
                backColor=None, # Remove background color
                leading=14, # Adjust line spacing
                leftIndent=5, # Align left with table content - adjust if needed
                rightIndent=0, # Remove right indent
                spaceBefore=15, # Add space before each order block
                alignment=1, # Center alignment
            )

            # Create a style for item details table - combined header and data styles
            item_table_style = TableStyle([
                # Header Row Styles
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#006400')), # Dark green header fill
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), # White text for header
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Center Align header text
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8), # Increased padding for header
                ('TOPPADDING', (0, 0), (-1, 0), 8), # Increased padding for header

                # Data Rows Styles (Item, Qty, Price, Total columns)
                ('ALIGN', (0, 1), (-1, -2), 'CENTER'), # Center align all data rows (excluding header and order total)
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -2), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -2), 6), # Increased padding for data
                ('TOPPADDING', (0, 1), (-1, -2), 6), # Increased padding for data

                # Alternating Row Colors for data rows
                ('BACKGROUND', (0, 1), (-1, -2), colors.white), # Default row background
                ('BACKGROUND', (0, 2), (-1, -2), colors.HexColor('#eeeeee')), # Lighter alternating row background

                # Grid and Box for the entire table
                ('GRID', (0, 0), (-1, -1), 0, colors.white), # No grid (based on previous requests)
                ('BOX', (0, 0), (-1, -1), 0, colors.white), # No box (based on previous requests)
                ('LEFTPADDING', (0, 0), (-1, -1), 5), # Add left padding to table content
                ('RIGHTPADDING', (0, 0), (-1, -1), 5), # Add right padding to table content

                # Styles for the 'Order Total' row (second to last row)
                ('SPAN', (0, -1), (2, -1)), # Span the first three columns for the 'Order Total' text
                ('ALIGN', (0, -1), (-1, -1), 'CENTER'), # Center align the Order Total row content
                ('LEFTPADDING', (0, -1), (0, -1), 5), # Add left padding to the 'Order Total' label
                ('BOTTOMPADDING', (0, -1), (-1, -1), 5), # Add bottom padding to the order total row
                ('TOPPADDING', (0, -1), (-1, -1), 5), # Add top padding to the order total row
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#006400')), # Dark green color for Order Total
            ])

            # Create a style for individual order total
            order_total_style = ParagraphStyle(
                'OrderTotalStyle',
                parent=styles['Normal'],
                spaceBefore=10, # Increased space before total
                spaceAfter=20, # Increased space after each order block
                fontSize=10,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#006400'), # Dark green color
                alignment=2, # Right align
                # Remove individual border, rely on main page border
                borderWidth=0,
                borderColor=None,
                borderPadding=0,
                rightIndent=10, # Adjust right indentation to align with total column
            )

            # Calculate grand total before iterating through orders
            grand_total = sum(order.get_total_bill() for order in orders)
            
            # Iterate through orders and add details + items
            for order in orders:
                # Calculate room details for this order
                room_charge = order.get_room_charge() if order.category else 0.0
                room_type = order.category.name if order.category else 'N/A'
                # Add order details paragraph
                order_details_text = f"Room No.: <b>{order.room_number or 'N/A'}</b> | Customer Name: {order.customer_name or 'N/A'} | Date: {order.check_in.strftime('%Y-%m-%d') if order.check_in else 'N/A'}"
                elements.append(Paragraph(order_details_text, order_details_style))

                # Fetch items for this order (already done in the view, but ensure it's available)
                order_items = order.roomorderitem_set.all()

                if order_items:
                    # Create table data for items, including header row
                    item_data = [['Item', 'Qty', 'Price', 'Total']]
                    for item in order_items:
                        item_data.append([
                            item.food.name,
                            str(item.quantity),
                            f"Rs {item.price:.2f}",
                            f"Rs {item.quantity * item.price:.2f}"
                        ])

                    # Create a style for bold text with black color
                    bold_style = ParagraphStyle(
                        'BoldText',
                        parent=styles['Normal'],
                        fontName='Helvetica-Bold',
                        fontSize=10,
                        textColor=colors.black,  # Black color for better readability
                        alignment=1,  # Center alignment
                        spaceAfter=5
                    )
                    
                    # Add the Order Total row (only food items) to the item data
                    order_total = Decimal(str(order.get_total_cost_of_orders()))
                    item_data.append([
                        Paragraph('Order Total:', bold_style),
                        '',
                        '',
                        Paragraph(f"Rs {order_total:.2f}", bold_style)
                    ])

                    # Add room charge with consistent styling
                    item_data.append([
                        Paragraph('Room Charge:', bold_style),
                        '',
                        '',
                        Paragraph(f"Rs {room_charge:.2f}" if room_charge != 0.0 else 'N/A', bold_style)
                    ])
                    # Add days stayed first
                    days_stayed = order.get_days_stayed()
                    item_data.append([
                        Paragraph('Days Stayed:', bold_style),
                        '',
                        '',
                        Paragraph(str(days_stayed) + ' days', bold_style)
                    ])

                    # Add grand total as a table row
                    grand_total = order.get_total_bill()
                    item_data.append([
                        Paragraph('Grand Total:', bold_style),
                        '',
                        '',
                        Paragraph(f"Rs {grand_total:.2f}", bold_style)
                    ])

                    # Create and style the item details table
                    # Adjust column widths for the item table relative to page width
                    item_col_widths = [doc.width*0.4, doc.width*0.1, doc.width*0.2, doc.width*0.2]
                    item_table = Table(item_data, colWidths=item_col_widths)

                    # Apply the combined style and add specific styles for the total row
                    style_list = [
                        # Header Row Styles
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')), # Orange header fill
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black), # Black text for header
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Center Align header text
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 15),  # Increased bottom padding for header
                        ('TOPPADDING', (0, 0), (-1, 0), 8),

                        # Data Rows Styles (Item, Qty, Price, Total columns)
                        ('ALIGN', (0, 1), (-1, -2), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -2), 8),
                        ('BOTTOMPADDING', (0, 1), (-1, -2), 10),  # Increased bottom padding for data rows
                        ('TOPPADDING', (0, 1), (-1, -2), 6),

                        # Special Rows Styles (Order Total, Room Charge, etc.)
                        ('FONTNAME', (0, -4), (-1, -1), 'Helvetica-Bold'),
                        ('TEXTCOLOR', (0, -4), (-1, -1), colors.black),
                        ('ALIGN', (0, -4), (-1, -1), 'CENTER'),
                        ('BOTTOMPADDING', (0, -4), (-1, -1), 15),  # Increased bottom padding for special rows
                        ('TOPPADDING', (0, -4), (-1, -1), 5),

                        # Grid and Box for the entire table
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Add grid lines
                        ('BOX', (0, 0), (-1, -1), 1, colors.black),   # Add box around table
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 5),

                        # Alternating Row Colors for data rows
                        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                        ('BACKGROUND', (0, 2), (-1, -2), colors.HexColor('#eeeeee'))
                    ]
                    
                    # Add alternating row colors for the item rows (excluding header and order total)
                    # The range is from the first data row (index 1) up to the second to last row (index -1 which is the order total)
                    for i in range(1, len(item_data) -1):
                        if i % 2 == 0: # Even index (0-based) after header (index 0)
                             style_list.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#eeeeee')))
                        else: # Odd index
                             style_list.append(('BACKGROUND', (0, i), (-1, i), colors.white))

                    item_table.setStyle(TableStyle(style_list))
                    elements.append(item_table)
                    # Add a Spacer between tables
                    elements.append(Spacer(1, 40))  # 40 points of space between tables

            # Add overall summary (Total Revenue) at the very end AFTER all order tables are added
            total_revenue = sum(order.get_total_bill() for order in orders)

            if orders: # Add overall total only if there are orders
                # Create a style for the overall total text
                overall_total_style = ParagraphStyle(
                    'OverallTotal',
                    parent=styles['Normal'],
                    fontSize=14,  # Larger font size
                    textColor=colors.red,  # Red color
                    fontName='Helvetica-Bold',  # Bold font
                    alignment=1  # Center alignment
                )

                # Create data for the overall total row
                overall_total_data_row = [
                    Paragraph('<b>Overall Total Revenue:</b>', overall_total_style),
                    '',
                    '',
                    Paragraph(f'<b>Rs {total_revenue:.2f}</b>', overall_total_style)
                ]

                # Create a table for the overall total to control its styling and column spanning
                # This table will only have one row (the overall total)
                # Use the same column widths as the item table for alignment
                item_col_widths = [doc.width*0.4, doc.width*0.1, doc.width*0.2, doc.width*0.2]
                overall_total_table = Table([overall_total_data_row], colWidths=item_col_widths)

                # Define style for the overall total table
                overall_total_style = TableStyle([
                    ('TOPBORDER', (0, 0), (-1, 0), 2, colors.black), # Add a top border above the overall total
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 5), # Add bottom padding
                    ('TOPPADDING', (0, 0), (-1, 0), 10), # Add top padding (more space above)
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.red), # Red color for text
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Center align the entire row
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Ensure bold font
                    ('FONTSIZE', (0, 0), (-1, 0), 14), # Larger font size
                ])

                # Apply style and add the overall total table to elements
                overall_total_table.setStyle(overall_total_style)
                elements.append(overall_total_table)
            else:
                elements.append(Paragraph("No orders found for the selected date range and payment method.", styles['Normal']))
            

    except Exception as e:
        elements.append(Paragraph(f"Error generating report: {str(e)}", styles['Normal']))

    # Build PDF
    try:
        doc.build(elements)
    except Exception as e:
        # Handle build errors gracefully by returning an error PDF or message
        error_response = HttpResponse(content_type='application/pdf')
        error_response['Content-Disposition'] = f'attachment; filename="sales_report_error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        error_doc = SimpleDocTemplate(error_response, pagesize=letter)
        error_elements = [Paragraph(f"Error generating PDF: {str(e)}", styles['Normal'])]
        error_doc.build(error_elements)
        return error_response

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