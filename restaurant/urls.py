from django.urls import path
from .views import index, signup_page, login_page, menu_view, add_to_cart, view_cart, remove_from_cart, confirm_order, aboutus, room,update_cart,get_cart, analytics_view, generate_sales_report_pdf, password_reset_request, password_reset_otp_verify, password_reset_confirm, signup_otp_verify
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.contrib.auth import views as auth_views



# Define your URL patterns first
urlpatterns = [
    path('', index, name='index'),
    path('signup/', signup_page, name='signup'),
    path('login/', login_page, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('menu/', menu_view, name='menu'),
    path('cart/add/<int:food_id>/', add_to_cart, name='add_to_cart'),
    path('cart/', view_cart, name='view_cart'),
    path('remove-cart-item/', remove_from_cart, name='remove_cart_item'),
    path('confirm-order/', confirm_order, name='confirm_order'),
    path('aboutus/', aboutus, name='aboutus'),
    path('room/', room, name='room'),
    path('update-cart/',update_cart, name='update_cart'),
    path('get_cart/',get_cart, name='get_cart'),
    path('api/website-visits/', views.website_visits, name='website_visits'),
    path('api/get-category-by-room-number/', views.get_category_by_room_number, name='get_category_by_room_number'),
    path('menu/access/<str:token>/', views.room_access, name='room_access'),
    # Password Reset URLs
    path('password_reset/', password_reset_request, name='password_reset'),
    path('password_reset/verify/', password_reset_otp_verify, name='password_reset_otp_verify'),
    path('password_reset/confirm/', password_reset_confirm, name='password_reset_confirm'),
    # Signup OTP Verification URL
    path('signup/verify-otp/', signup_otp_verify, name='signup_otp_verify'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
