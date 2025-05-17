from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Food, WebsiteVisit, Profile, DashboardStats, Room, RoomCategory, RoomOrder, RoomOrderItem, Cart, CartItem
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import path
from .views import analytics_view, generate_sales_report_pdf

# Customizing Food admin view
class FoodAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'display_image')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "No Image"
    display_image.short_description = 'Image'

class RoomOrderItemInline(admin.TabularInline):
    model = RoomOrderItem
    extra = 0
    fields = ('food', 'quantity', 'price', 'status')
    readonly_fields = ('price',)

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
            return queryset.filter(check_in__gte=since)
        elif self.value() == 'week':
            since = now - timedelta(days=7)
            return queryset.filter(check_in__gte=since)
        elif self.value() == 'month':
            since = now - timedelta(days=30)
            return queryset.filter(check_in__gte=since)
        return queryset

@admin.register(RoomOrder)
class RoomOrderAdmin(admin.ModelAdmin):
    inlines = [RoomOrderItemInline]
    list_display = ('room_number', 'category', 'check_in', 'check_out', 'is_active', 'status', 'payment_method', 'analytics_link')
    search_fields = ('room_number',)
    list_filter = ('is_active', 'category', 'status', 'payment_method')
    list_per_page = 10
    fieldsets = (
        (None, {
            'fields': ('room_number', 'customer_name', 'category', 'check_in', 'check_out', 'is_active', 'is_paid', 'status', 'payment_method'),
        }),
        ('Bill Information', {
            'fields': ('bill_payments_section',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('bill_payments_section',)

    def get_total_bill(self, obj):
        return f"₹{obj.get_total_bill():.2f}"
    get_total_bill.short_description = "Total Bill"

    def bill_payments_section(self, obj):
        if not obj or not obj.pk:
            return "Save and add items to see the bill."

        try:
            # Ensure calculations result in floats
            days_stayed = int(obj.get_days_stayed())
            room_charge_float = float(obj.get_room_charge())
            total_cost_of_orders_float = float(obj.get_total_cost_of_orders())
            grand_total_float = float(obj.get_grand_total())
            paid = obj.is_paid
            from django.utils.safestring import mark_safe
            status_html_content = (
                '<span style="background:#d4edda;color:#155724;padding:3px 12px;border-radius:12px;font-weight:bold;border:1px solid #c3e6cb;">Paid</span>'
                if paid else
                '<span style="background:#f8d7da;color:#721c24;padding:3px 12px;border-radius:12px;font-weight:bold;border:1px solid #f5c6cb;">Unpaid</span>'
            )

            # Format check_out date if available
            bill_date = obj.check_out.strftime('%Y-%m-%d %H:%M') if obj.check_out else "N/A"

            # Build the ordered items table HTML
            items_table_html = """
            <table style="width:100%;border-collapse:collapse;margin-top:20px;">
                <thead>
                    <tr style="background-color:#f8f9fa;">
                        <th style="text-align:left;padding:10px 12px;border-bottom:1px solid #dee2e6;">Item</th>
                        <th style="text-align:center;padding:10px 12px;border-bottom:1px solid #dee2e6;">Quantity</th>
                        <th style="text-align:right;padding:10px 12px;border-bottom:1px solid #dee2e6;">Rate</th>
                        <th style="text-align:right;padding:10px 12px;border-bottom:1px solid #dee2e6;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
            """

            if hasattr(obj, 'roomorderitem_set') and obj.roomorderitem_set.exists():
                for item in obj.roomorderitem_set.all():
                    # Ensure item.price is treated as a float for calculation and format it
                    item_price_float = float(item.price)
                    item_subtotal = item.quantity * item_price_float
                    items_table_html += format_html(
                        """
                        <tr>
                            <td style="text-align:left;padding:10px 12px;border-bottom:1px solid #dee2e6;">{}</td>
                            <td style="text-align:center;padding:10px 12px;border-bottom:1px solid #dee2e6;">{}</td>
                            <td style="text-align:right;padding:10px 12px;border-bottom:1px solid #dee2e6;">₹{}</td>
                            <td style="text-align:right;padding:10px 12px;border-bottom:1px solid #dee2e6;">₹{}</td>
                        </tr>
                        """,
                        item.food.name if item.food else "N/A",
                        item.quantity,
                        f"{item_price_float:.2f}", # Format to string here
                        f"{item_subtotal:.2f}" # Format to string here
                    )
            else:
                 items_table_html += '<tr><td colspan="4" style="text-align:center;padding:10px 12px;">No items ordered yet.</td></tr>'

            items_table_html += """
                </tbody>
            </table>
            """

            # Format numeric values to strings before passing to format_html
            room_charge_str = f"{room_charge_float:.2f}"
            total_cost_of_orders_str = f"{total_cost_of_orders_float:.2f}"
            grand_total_str = f"{grand_total_float:.2f}"

            # Get the static URL for the logo
            logo_url = staticfiles_storage.url('images/qr.png')

            # Construct the full HTML template with simple placeholders
            full_html_template = """
                <div id="bill-section" style="max-width:600px;margin:20px auto;padding:30px;border:1px solid #e0e0e0;border-radius:10px;font-family:Arial, sans-serif;background-color:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.05);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding-bottom:20px;border-bottom:2px solid #f0f0f0;">
                        <div style="text-align:left;">
                             <img src="{}" alt="Company Logo" style="max-height: 80px; margin-bottom: 10px;">
                            <p style="margin:5px 0 0 0;font-size:0.9em;color:#777;">Invoice No: <strong>{}</strong></p>
                            <p style="margin:0;font-size:0.9em;color:#777;">Date: <strong>{}</strong></p>
                        </div>
                        <div style="text-align:right;">
                            <h2 style="margin:0;color:#555;font-size:1.5em;">Bhanjyang Village and Lodge</h2>
                            <p style="margin:5px 0 0 0;font-size:0.9em;color:#777;">Sarankot</p>
                            <p style="margin:0;font-size:0.9em;color:#777;">Pokhara,Nepal</p>
                            <p style="margin:0;font-size:0.9em;color:#777;">Phone: +977 974-5522082</p>
                        </div>
                    </div>

                    <div style="margin-bottom:30px;padding-bottom:20px;border-bottom:1px solid #eee;">
                        <h4 style="margin-top:0;margin-bottom:10px;color:#555;border-bottom:1px dashed #eee;padding-bottom:5px;">Bill To:</h4>
                        <p style="margin:5px 0;font-size:1.1em;"><strong>Room Number:</strong> {}</p>
                        <p style="margin:5px 0;font-size:1.1em;"><strong>Customer Name:</strong> {}</p>
                    </div>

                    {}

                    <div style="margin-top:20px;padding-top:20px;border-top:1px solid #eee;">
                        <div style="display:flex;justify-content:flex-end;">
                            <div style="width:200px; margin-bottom: 10px;">
                                <p style="margin:5px 0;"><strong>Days Stayed:</strong> <span style="float:right;">{}</span></p>
                                <p style="margin:5px 0;"><strong>Room Charge:</strong> <span style="float:right;">₹{}</span></p>
                                <p style="margin:5px 0;"><strong>Total Item Cost:</strong> <span style="float:right;">₹{}</span></p>
                            </div>
                        </div>
                        <p style="display: flex; justify-content: space-between; margin:15px 0 5px 0;font-size:1.4em;font-weight:bold;color:#28a745;border-top:1px solid #eee;padding-top:10px;"><span style="white-space: nowrap;">Grand Total:</span> <span>₹{}</span></p>
                    </div>

                    <div style="text-align:center;padding-top:20px;border-top:1px solid #eee;margin-top:20px;">
                        <p style="margin:0;font-size:1.1em;"><strong>Payment Status:</strong> {}</p>
                    </div>
                </div>
                <button type="button" onclick="printBillSection()" style="display:block;margin:20px auto;padding:12px 30px;background:#007bff;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:1.1em;transition:background-color 0.3s ease;" onmouseover="this.style.backgroundColor='#0056b3'" onmouseout="this.style.backgroundColor='#007bff'">Print Bill</button>
                <script>
                function printBillSection() {{
                    var printContents = document.getElementById('bill-section').innerHTML;
                    var originalContents = document.body.innerHTML;
                    document.body.innerHTML = printContents;
                    window.print();
                    document.body.innerHTML = originalContents;
                    location.reload();
                }}
                </script>
                """

            return format_html(
                full_html_template,
                logo_url,
                obj.pk,
                bill_date,
                obj.room_number,
                obj.customer_name if obj.customer_name else "N/A",
                mark_safe(items_table_html),
                days_stayed,
                room_charge_str,
                total_cost_of_orders_str,
                grand_total_str,
                mark_safe(status_html_content)
            )
        except Exception as e:
            return f"Error calculating bill: {e}"
    bill_payments_section.short_description = "Bill Payments"

    def analytics_link(self, obj):
        return format_html(f'<a href="/admin/restaurant/roomorder/analytics/">View Analytics</a>')
    analytics_link.short_description = 'Analytics'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_site.admin_view(analytics_view), name='roomorder_analytics'),
            path('analytics/pdf/<str:from_date>/<str:to_date>/', self.admin_site.admin_view(generate_sales_report_pdf), name='restaurant_generate_sales_report_pdf_all'),
            path('analytics/pdf/<str:from_date>/<str:to_date>/<str:payment_method>/', self.admin_site.admin_view(generate_sales_report_pdf), name='restaurant_generate_sales_report_pdf'),
        ]
        return custom_urls + urls

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(RoomCategory)
class RoomCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_per_night', 'room_numbers')
    search_fields = ('name',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'size', 'capacity', 'bed', 'services', 'display_image')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "No Image"
    display_image.short_description = 'Image'

@admin.register(WebsiteVisit)
class WebsiteVisitAdmin(admin.ModelAdmin):
    list_display = ('count',)
    readonly_fields = ('count',)
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(DashboardStats)
class DashboardStatsAdmin(admin.ModelAdmin):
    list_display = ('rooms', 'happy_guests', 'dishes_served', 'staff_members')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_photo')

    def display_photo(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="50" height="50" />', obj.photo.url)
        return "No Photo"
    display_photo.short_description = 'Photo'