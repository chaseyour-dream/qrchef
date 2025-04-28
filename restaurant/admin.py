from django.contrib import admin
from django.utils.html import format_html
from .models import Category, FoodItem, Order, OrderItem, WebsiteVisit, Profile, DashboardStats, Room
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone

# Customizing FoodItem admin view
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'image_url')
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


class OrderDateRangeFilter(admin.SimpleListFilter):
    title = 'Order Date Range'
    parameter_name = 'order_date_range'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today (24 hrs)'),
            ('week', 'Last 7 Days'),
            ('month', 'Last 30 Days'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            since = now - timedelta(days=1)
            return queryset.filter(created_at__gte=since)
        elif self.value() == 'week':
            since = now - timedelta(days=7)
            return queryset.filter(created_at__gte=since)
        elif self.value() == 'month':
            since = now - timedelta(days=30)
            return queryset.filter(created_at__gte=since)
        return queryset



class OrderAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'created_at', 'total_price', 'status', 'payment_method', 'payment_status', 'order_details')
    inlines = [OrderItemInline]
    list_per_page = 20  # Show 20 orders per page
    list_filter = (OrderDateRangeFilter, 'room_number', 'status')
    actions = ['delete_all_orders']

    def delete_all_orders(self, request, queryset):
        from .models import Order
        count = Order.objects.count()
        Order.objects.all().delete()
        self.message_user(request, f"Deleted all {count} orders.", messages.SUCCESS)
    delete_all_orders.short_description = "Delete ALL orders (careful!)"

    def order_details(self, obj):
        details = [f"{item.food_item.name} (x{item.quantity})" for item in obj.orderitem_set.all()]
        return ", ".join(details)
    order_details.short_description = 'Order Details'

# Customizing Category admin view
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


# Register models with admin site
class WebsiteVisitAdmin(admin.ModelAdmin):
    readonly_fields = ('count',)

admin.site.register(WebsiteVisit, WebsiteVisitAdmin)
class DashboardStatsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Allow add only if no instance exists
        count = DashboardStats.objects.count()
        return count == 0

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False

admin.site.register(DashboardStats, DashboardStatsAdmin)
admin.site.register(FoodItem, FoodItemAdmin)
admin.site.register(Order, OrderAdmin)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "size", "capacity", "bed", "services")
    search_fields = ("name", "size", "capacity", "bed", "services")

admin.site.register(Room, RoomAdmin)
admin.site.register(Category, CategoryAdmin)