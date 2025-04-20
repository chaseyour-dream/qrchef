from django.views.decorators.csrf import csrf_protect 
from django.views.decorators.csrf import csrf_exempt 
from django.shortcuts import render,redirect
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.models import User
from restaurant.models import FoodItem, Category, CartItem, Order, OrderItem, Payment
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
import json
import decimal
import logging



# Home Page
def index(request):
    return render(request, 'index.html')

# Signup Page
def signup_page(request):
    return render(request, 'signup.html')

# Login Page
def login_page(request):
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

    # 2. Usual menu logic
    food_items = FoodItem.objects.select_related('category').all()
    category_food_items = {}
    for item in food_items:
        category_food_items.setdefault(item.category, []).append(item)

    return render(request, 'menu.html', {'category_food_items': category_food_items})

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

# Place Order (Create order and clear cart)
@login_required
def place_order(request):
    user = request.user
    cart = request.session.get('cart', {})

    if not cart:
        return JsonResponse({'message': 'Your cart is empty, add items before placing an order'}, status=400)

    order = Order.objects.create(user=user, total_price=0)
    total_price = decimal.Decimal(0.00)

    for food_id, food_data in cart.items():
        try:
            food_item = FoodItem.objects.get(id=food_id)
            quantity = food_data['quantity']
            price = decimal.Decimal(food_item.price) * decimal.Decimal(quantity)
            total_price += price

            OrderItem.objects.create(
                order=order,
                food_name=food_item.name,
                price=price,
                quantity=quantity  # Added quantity tracking
            )
        except FoodItem.DoesNotExist:
            return JsonResponse({'message': f'Food item with ID {food_id} not found'}, status=404)

    order.total_price = total_price
    order.save()

    request.session['cart'] = {}
    request.session.modified = True

    return JsonResponse({'message': 'Order placed successfully', 'order_id': order.id, 'total_price': float(total_price)})

logger = logging.getLogger(__name__)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def confirm_order(request):
    if request.method == 'POST':
        try:
            if request.content_type.startswith('multipart/form-data'):
                user = request.user if request.user.is_authenticated else None
                items = json.loads(request.POST.get('items', '[]'))
                payment_method = request.POST.get('payment_method', 'Cash')
                payment_proof = request.FILES.get('payment_proof')
            else:
                data = json.loads(request.body)
                user = request.user if request.user.is_authenticated else None
                items = data.get('items', [])
                payment_method = data.get('payment_method', 'Cash')
                payment_proof = None

            # Always get room number from session (set by menu_view)
            room_number = request.session.get('room_no', '')

            if not items:
                return JsonResponse({'success': False, 'message': 'No items in order'}, status=400)

            total_price = sum(float(item['price']) * int(item['quantity']) for item in items)
            order = Order.objects.create(
                user=user,
                total_price=total_price,
                status='Pending',
                room_number=room_number,
                quantity=sum(int(item['quantity']) for item in items)
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    food_item=FoodItem.objects.get(id=item['id']),
                    price=float(item['price']),
                    quantity=int(item['quantity'])
                )

            Payment.objects.create(
                user=user,
                order_id=order.id,
                amount=total_price,
                payment_method=payment_method,
                payment_status='Completed' if payment_method == 'Cash' else 'Pending',
                payment_proof=payment_proof
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

def website_visits(request):
    visits = cache.get('website_visits', 0) + 1
    cache.set('website_visits', visits, None)  # No expiry
    return JsonResponse({'visits': visits})