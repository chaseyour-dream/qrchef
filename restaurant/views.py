from django.views.decorators.csrf import csrf_protect 
from django.views.decorators.csrf import csrf_exempt 
from django.shortcuts import render,redirect
from .forms import ProfileImageForm
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from restaurant.models import FoodItem, Category, Order, OrderItem
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from .models import WebsiteVisit
import json
import logging



# Home Page
def index(request):
    if request.user.is_authenticated:
        from .models import Profile
        Profile.objects.get_or_create(user=request.user)
    from .models import DashboardStats
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
    from .models import Profile
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
            from .models import Profile
            Profile.objects.get_or_create(user=user)
            return redirect('index')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

# Room Page
def room(request):
    return render(request, 'room.html')

# About Us Page
def aboutus(request):
    return render(request, 'aboutus.html')

# Menu Page
logger = logging.getLogger(__name__)
def menu_view(request):
    # 1. Capture room number from URL if present
    room_no = request.GET.get('room')
    if room_no:
        request.session['room_no'] = room_no

    categories = Category.objects.all()
    category_id = request.GET.get('category')
    if category_id:
        food_items = FoodItem.objects.filter(category_id=category_id)
        categories = categories.filter(id=category_id)
    else:
        food_items = FoodItem.objects.all()

    # Attach items to each category
    for category in categories:
        category.items = food_items.filter(category=category)
    cart_items = []
    cart = request.session.get('cart', {})
    for item_id, quantity in cart.items():
        try:
            food_item = FoodItem.objects.get(id=item_id)
            cart_items.append({'food_item': food_item, 'quantity': quantity})
        except FoodItem.DoesNotExist:
            pass
    context = {
        'categories': categories,
        'food_items': food_items,
        'cart_items': cart_items,
    }
    return render(request, 'menu.html', context)

# API to fetch cart data
def get_cart(request):
    cart = request.session.get("cart", {})
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    return JsonResponse({"cart": cart, "total_price": float(total_price)})

# Update Cart (Add items or update quantities)
def update_cart(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            cart = request.session.get("cart", {})

            item_id = str(data["id"])
            item_name = data["name"]
            item_price = float(data["price"])

            if item_id in cart:
                cart[item_id]["quantity"] += 1
            else:
                cart[item_id] = {"name": item_name, "price": item_price, "quantity": 1}

            request.session["cart"] = cart
            request.session.modified = True

            return JsonResponse({"success": True, "cart": cart})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid request"})

# Add Food Item to Cart
def add_to_cart(request, food_id):
    cart = request.session.setdefault('cart', {})

    try:
        food_item = FoodItem.objects.get(id=food_id)
        if str(food_id) in cart:
            cart[str(food_id)]['quantity'] += 1
        else:
            cart[str(food_id)] = {
                'name': food_item.name,
                'price': float(food_item.price),
                'quantity': 1,
                'image_url': food_item.image_url
            }
        request.session.modified = True
        return JsonResponse({'message': 'Item added to cart', 'cart': cart})
    except FoodItem.DoesNotExist:
        return JsonResponse({'message': 'Food item not found'}, status=404)

# View Cart
def view_cart(request):
    cart = request.session.get('cart', {})
    total_price = sum(item["price"] * item["quantity"] for item in cart.values())
    return render(request, 'cart.html', {'cart': cart, 'total_price': total_price})

# Remove Item from Cart
@csrf_exempt
def remove_from_cart(request):
    item_id = request.POST.get('item_id')
    
    # Fetch the current cart from the session
    cart = request.session.get('cart', {})

    if item_id in cart:
        # If the item is in the cart, remove it
        del cart[item_id]
        request.session['cart'] = cart
        return JsonResponse({'message': 'Item removed from cart'}, status=200)
    else:
        # If the item is not in the cart, return a bad request response
        return JsonResponse({'error': 'Item not found in cart'}, status=400)

# Order placement is now handled by confirm_order, which supports AJAX, room number, payment method, and both authenticated/anonymous users.
# The old place_order view has been removed for clarity and to prevent duplicates.

logger = logging.getLogger(__name__)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def confirm_order(request):
    import logging
    logger = logging.getLogger('django')
    if request.method == 'POST':
        try:
            logger.info('Incoming confirm_order request: content_type=%s', request.content_type)
            if request.content_type.startswith('multipart/form-data'):
                user = request.user if request.user.is_authenticated else None
                items = json.loads(request.POST.get('items', '[]'))
                payment_method = request.POST.get('payment_method', 'Cash')
                payment_proof = request.FILES.get('payment_proof')
                room_number = request.POST.get('room_no', '')
                logger.info('Parsed multipart: user=%s, items=%s, payment_method=%s, payment_proof=%s, room_no=%s', user, items, payment_method, payment_proof, room_number)
            else:
                data = json.loads(request.body)
                user = request.user if request.user.is_authenticated else None
                items = data.get('items', [])
                payment_method = data.get('payment_method', 'Cash')
                payment_proof = None
                room_number = data.get('room_no', '')
                logger.info('Parsed JSON: user=%s, items=%s, payment_method=%s, room_no=%s', user, items, payment_method, room_number)

            if not room_number:
                logger.warning('No room number provided')
                return JsonResponse({'success': False, 'message': 'Room number is required. Please scan the QR code.'}, status=400)

            if not items:
                logger.warning('No items in order')
                return JsonResponse({'success': False, 'message': 'No items in order'}, status=400)

            total_price = sum(float(item['price']) * int(item['quantity']) for item in items)
            logger.info('Calculated total_price: %s', total_price)
            order = Order.objects.create(
                total_price=total_price,
                status='Pending',
                room_number=room_number,
                quantity=sum(int(item['quantity']) for item in items)
            )
            logger.info('Order created: %s', order)

            for item in items:
                food_item = FoodItem.objects.get(id=item['id'])
                OrderItem.objects.create(
                    order=order,
                    food_item=food_item,
                    price=float(item['price']),
                    quantity=int(item['quantity'])
                )
                logger.info('OrderItem created for food_item=%s, quantity=%s', food_item, item['quantity'])

            # Set payment fields directly on the order
            order.payment_method = payment_method
            order.payment_status = 'Pending' if payment_method == 'Cash' else 'Completed'
            order.payment_proof = payment_proof if payment_method == 'E-Payment' else None
            order.save()
            logger.info('Order updated with payment_method=%s, payment_status=%s', payment_method, order.payment_status)

            return JsonResponse({'success': True})
        except Exception as e:
            logger.error('Order creation failed: %s', e, exc_info=True)
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    logger.warning('Invalid request method')
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


def website_visits(request):
    visits_obj, created = WebsiteVisit.objects.get_or_create(pk=1)
    visits_obj.count += 1
    visits_obj.save()
    return JsonResponse({'visits': visits_obj.count})   