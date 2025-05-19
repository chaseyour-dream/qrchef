from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Food Categories'
    
    def __str__(self):
        return self.name

class Food(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class RoomCategory(models.Model):
    name = models.CharField(max_length=50)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2)
    room_numbers = models.TextField(
        help_text="Enter room numbers separated by commas (e.g., '101,102,103')",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name_plural = 'Room Categories'

    def get_room_numbers_list(self):
        if not self.room_numbers:
            return []
        return [num.strip() for num in self.room_numbers.split(',') if num.strip()]

    def add_room_number(self, room_number):
        current_numbers = self.get_room_numbers_list()
        if room_number not in current_numbers:
            current_numbers.append(room_number)
            self.room_numbers = ','.join(current_numbers)
            self.save()

    def remove_room_number(self, room_number):
        current_numbers = self.get_room_numbers_list()
        if room_number in current_numbers:
            current_numbers.remove(room_number)
            self.room_numbers = ','.join(current_numbers)
            self.save()

    def __str__(self):
        return self.name
    
class Room(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='rooms/')
    size = models.CharField(max_length=50)
    capacity = models.CharField(max_length=50)
    bed = models.CharField(max_length=50)
    services = models.CharField(max_length=200)
    category = models.ForeignKey(RoomCategory, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"
    
class RoomOrder(models.Model):
    room_number = models.CharField(max_length=10, null=True, blank=True)
    customer_name = models.CharField(max_length=200, null=True, blank=True)
    category = models.ForeignKey(RoomCategory, on_delete=models.SET_NULL, null=True, blank=True)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)
    payment_time = models.DateTimeField(null=True, blank=True)
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='confirmed'
    )
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Online Payment', 'Online Payment'),
        # Add other payment methods here if needed
    ]
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,  # Allow null for existing records
        blank=True
    )

    def get_days_stayed(self):
        if not self.check_in:
            return 0
        end = self.check_out or timezone.now()
        return (end.date() - self.check_in.date()).days or 1

    def get_room_charge(self):
        if self.category:
            try:
                val = float(self.get_days_stayed()) * float(self.category.price_per_night)
                print("DEBUG get_room_charge:", val, type(val))
                return val
            except Exception as e:
                print("ERROR get_room_charge:", e)
                return 0.0
        return 0.0

    def get_total_items(self):
        return sum(item.quantity for item in self.roomorderitem_set.all())

    def get_total_cost_of_orders(self):
        total = 0.0
        for item in self.roomorderitem_set.all():
            try:
                val = float(item.quantity) * float(item.price)
                print("DEBUG get_total_cost_of_orders item:", val, type(val))
                total += val
            except Exception as e:
                print("ERROR get_total_cost_of_orders item:", e)
                continue
        print("DEBUG get_total_cost_of_orders total:", total, type(total))
        return total

    def get_grand_total(self):
        try:
            val = float(self.get_room_charge()) + float(self.get_total_cost_of_orders())
            print("DEBUG get_grand_total:", val, type(val))
            return val
        except Exception as e:
            print("ERROR get_grand_total:", e)
            return 0.0

    def get_nights(self):
        if self.check_in and self.check_out:
            nights = (self.check_out.date() - self.check_in.date()).days
            return max(nights, 1)
        return 1

    def get_total_bill(self):
        room_charge = Decimal(str(self.get_room_charge()))
        order_total = sum(Decimal(str(item.get_total_price())) for item in self.roomorderitem_set.all())
        return room_charge + order_total

    def __str__(self):
        return f"Order for Room {self.room_number}"

class RoomOrderItem(models.Model):
    room_order = models.ForeignKey(RoomOrder, on_delete=models.CASCADE)
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='confirmed'
    )

    def __str__(self):
        return f"{self.quantity} x {self.food.name} in {self.room_order}"

    def get_total_price(self):
        return self.quantity * self.price

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart {self.id}"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.cartitem_set.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    room_order = models.ForeignKey(RoomOrder, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.food.name} in {self.cart}"

    def get_total_price(self):
        return self.quantity * self.food.price

class WebsiteVisit(models.Model):
    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Website Visits: {self.count}"

class DashboardStats(models.Model):
    rooms = models.PositiveIntegerField(default=0)
    happy_guests = models.PositiveIntegerField(default=0)
    dishes_served = models.PositiveIntegerField(default=0)
    staff_members = models.PositiveIntegerField(default=0)
    dishes_limit = models.PositiveIntegerField(default=10000, help_text="Limit for Dishes Served animation")
    guests_limit = models.PositiveIntegerField(default=2000, help_text="Limit for Happy Guests animation")
    
    class Meta:
        verbose_name_plural = 'Dashboard Stats'

    def __str__(self):
        return "Dashboard Stats"


# User Profile for photo upload
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    def get_avatar_url(self):
        if self.photo:
            return self.photo.url
        return None

# Signal to create or update Profile automatically
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        try:
            instance.profile.save()
        except Profile.DoesNotExist:
            Profile.objects.create(user=instance)

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.user.username}"

    def is_valid(self):
        # OTP is valid for 10 minutes
        return (timezone.now() - self.created_at) < timedelta(minutes=10) and not self.is_used

class SignupOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    temp_password = models.CharField(max_length=128)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], null=True, blank=True)

    def __str__(self):
        return f"Signup OTP for {self.email}"

    def is_valid(self):
        # OTP is valid for 10 minutes
        return (timezone.now() - self.created_at) < timedelta(minutes=10) and not self.is_used
            

