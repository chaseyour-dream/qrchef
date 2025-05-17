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
from .models import WebsiteVisit, DashboardStats, Profile
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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch



# Home Page
def index(request):
    if request.user.is_authenticated:
        Profile.objects.get_or_create(user=request.user)
    stats = DashboardStats.objects.first()
    return render(request, 'index.html', {'stats': stats})

# Signup Page
import random
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings

def signup_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        email = request.POST.get('email')
        if not username or not password or not password2:
            messages.error(request, 'All fields are required.')
        elif password != password2:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
        else:
            user = User.objects.create_user(username=username, password=password, email=email)
            user.save()
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
    return render(request, 'signup.html')

# (verify_otp view removed)

# Logout Page
def logout_view(request):
    logout(request)
    return redirect('login')

# Profile Page


from django.contrib import messages

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
            login(request, user)
            # Robust: always ensure profile exists
            Profile.objects.get_or_create(user=user)
            return redirect('index')
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
        try:
            data = json.loads(request.body)
            room_no = data.get('room_no')
            items = data.get('items', [])
            
            if not room_no:
                return JsonResponse({"success": False, "error": "Room number is required"}, status=400)
            
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
    orders = None
    from_date = request.POST.get('from_date')
    to_date = request.POST.get('to_date')
    payment_method = request.POST.get('payment_method')

    if request.method == 'POST':
        if from_date and to_date:
            try:
                from_datetime = datetime.strptime(from_date, '%Y-%m-%d')
                to_datetime = datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)
                orders = RoomOrder.objects.filter(
                    check_in__gte=from_datetime,
                    check_in__lt=to_datetime
                )

                if payment_method:
                    orders = orders.filter(payment_method=payment_method)

                # Calculate total revenue
                total_revenue = sum(order.get_total_bill() for order in orders) if orders else 0

            except ValueError:
                # Handle invalid date format
                pass # Or add an error message

    context = {
        'orders': orders,
        'from_date': from_date,
        'to_date': to_date,
        'payment_method': payment_method,
        'payment_method_choices': RoomOrder.PAYMENT_METHOD_CHOICES,
        'total_revenue': total_revenue if 'total_revenue' in locals() else 0, # Pass total revenue to template
    }
    return render(request, 'admin/restaurant/roomorder/analytics.html', context)   

@user_passes_test(lambda u: u.is_staff)
def generate_sales_report_pdf(request, from_date=None, to_date=None, payment_method=None):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{datetime.now().strftime("%Y%m%d")}.pdf"'

    # Create the PDF object
    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Add title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=15,
        alignment=1
    )
    elements.append(Paragraph("Sales Report", title_style))

    # Add date range
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=20,
        alignment=1
    )
    date_text = f"Period: {from_date} to {to_date}"
    if payment_method:
        date_text += f" (Payment Method: {dict(RoomOrder.PAYMENT_METHOD_CHOICES).get(payment_method, payment_method)})"
    elements.append(Paragraph(date_text, date_style))
    elements.append(Spacer(1, 10))

    # Get orders data and build report elements
    try:
        from_datetime = datetime.strptime(from_date, '%Y-%m-%d')
        to_datetime = datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)
        orders = RoomOrder.objects.filter(
            check_in__gte=from_datetime,
            check_in__lt=to_datetime
        ).order_by('check_in') # Order by check-in date

        if payment_method:
            orders = orders.filter(payment_method=payment_method)

        if orders:
            # Create table data for the main report table
            data = [['Room No.', 'Customer Name', 'Amount', 'Date']]
            
            for order in orders:
                data.append([
                    str(order.room_number),
                    order.customer_name or 'N/A',
                    f"₹{order.get_total_bill():.2f}",
                    order.check_in.strftime('%Y-%m-%d') if order.check_in else 'N/A', # Using check-in date as the order date
                ])

            # Create the main report table
            col_widths = [doc.width/6, doc.width/3, doc.width/6, doc.width/6]
            table = Table(data, colWidths=col_widths)

            # Style for the main report table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.ReportLabGreen), # Professional header color
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige), # Light background for rows
                ('GRID', (0, 0), (-1, -1), 1, colors.black), # Add grid lines
                ('BOX', (0, 0), (-1, -1), 1, colors.black), # Add border around table
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'), # Right align Amount
                ('ALIGN', (0, 1), (0, -1), 'LEFT'), # Left align Room No.
                ('ALIGN', (1, 1), (1, -1), 'LEFT'), # Left align Customer Name
                ('ALIGN', (3, 1), (3, -1), 'CENTER'), # Center align Date
            ]))

            elements.append(table)

            # Add overall summary (Total Revenue)
            total_revenue = sum(order.get_total_bill() for order in orders)
            
            # Summary style for Total Revenue
            total_revenue_style = ParagraphStyle(
                'TotalRevenueStyle',
                parent=styles['Heading2'], # Use a slightly larger style for summary
                spaceBefore=20,
                alignment=2 # Right align summary
            )
            
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"Total Revenue: ₹{total_revenue:.2f}", total_revenue_style))

        else:
            elements.append(Paragraph("No orders found for the selected date range and payment method.", styles['Normal']))

    except Exception as e:
        elements.append(Paragraph(f"Error generating report: {str(e)}", styles['Normal']))

    # Build PDF
    doc.build(elements)
    return response   