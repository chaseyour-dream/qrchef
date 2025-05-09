from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    room_number = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    quantity = models.IntegerField(default=1)
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash on Delivery'),
        ('E-Payment', 'E-Payment'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    payment_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)

    def __str__(self):
        return f"Order {self.id} - Room {self.room_number}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.food_item.name} - {self.quantity}'

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"{self.food_item.name} (x{self.quantity})"

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

class Room(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='rooms/')
    size = models.CharField(max_length=50)
    capacity = models.CharField(max_length=50)
    bed = models.CharField(max_length=50)
    services = models.CharField(max_length=200)

    def __str__(self):
        return self.name

# User Profile for photo upload
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

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
            

