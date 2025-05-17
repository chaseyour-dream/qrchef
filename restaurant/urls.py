from django.urls import path
from .views import index, signup_page, login_page, menu_view, add_to_cart, view_cart, remove_from_cart, confirm_order, aboutus, room,update_cart,get_cart, analytics_view, generate_sales_report_pdf
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
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='password_reset.html',
        email_template_name='password_reset_email.html',
        subject_template_name='password_reset_subject.txt'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='password_reset_complete.html'
    ), name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
