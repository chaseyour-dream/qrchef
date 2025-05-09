from django.urls import path
from .views import index, signup_page, login_page, menu_view, add_to_cart, view_cart, remove_from_cart, confirm_order, aboutus, room,update_cart,get_cart
from django.conf import settings
from django.conf.urls.static import static
from . import views



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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
