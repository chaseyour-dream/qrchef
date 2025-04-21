from django.contrib import admin
from django.utils.html import format_html
from .models import Category, FoodItem, Order, CartItem, OrderItem

# Customizing FoodItem admin view
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'description', 'image_url')
    search_fields = ('name',)

    def image_url(self, obj):
        if obj.image:
            return obj.image.url
        return "No image"
    image_url.short_description = 'Image URL'

# Customizing CartItem admin view
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('food_item', 'quantity', 'order_room_number')
    list_filter = ('order__room_number',)

    def order_room_number(self, obj):
        return obj.order.room_number
    order_room_number.short_description = 'Room Number'

# Customizing Order admin view
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('food_item', 'price', 'quantity')

# Customizing Order admin view
class OrderAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'created_at', 'total_price', 'status', 'payment_method', 'payment_status', 'order_details', 'show_payment_proof')
    inlines = [OrderItemInline]

    def order_details(self, obj):
        details = [f"{item.food_item.name} (x{item.quantity})" for item in obj.orderitem_set.all()]
        return ", ".join(details)
    order_details.short_description = 'Order Details'

    def show_payment_proof(self, obj):
        if obj.payment_proof:
            return format_html('<img src="{}" width="80" />', obj.payment_proof.url)
        return "-"
    show_payment_proof.short_description = 'Payment Proof'

# Customizing Category admin view
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')


# Register models with admin site
admin.site.register(FoodItem, FoodItemAdmin)
admin.site.register(CartItem, CartItemAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Category, CategoryAdmin)