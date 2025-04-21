from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    room_number = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/', null=True, blank=True)

    def __str__(self):
        user_display = self.user.username if self.user else "Guest"
        return f"Order {self.id} - {user_display}"

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

class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    order_id = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, default="Cash")
    payment_status = models.CharField(max_length=20, default="Pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_proof = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)  # For e-payment screenshot
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.order_id} - {self.payment_status}"
    
class WebsiteVisit(models.Model):
    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Website Visits: {self.count}"