"""
URL configuration for orders project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django_rest_passwordreset.views import reset_password_request_token
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet, ConfirmEmailView, PartnerProductView, \
    PartnerStateView, ShopView, CategoryView, ProductView, ContactView, \
    BasketView, OrderViewSet, BuyerSellerOrderView, PartnerOrderView, AuthenticateView, CustomResetPasswordConfirm

router = DefaultRouter()
router.register('partner/products', PartnerProductView, basename='partner')
router.register('shops', ShopView, basename='shops')
router.register('categories', CategoryView, basename='categories')
router.register('products', ProductView, basename='products')
router.register('user/contact', ContactView, basename='contacts')
router.register('order', OrderViewSet, basename='order')
router.register('order/seller_order', BuyerSellerOrderView, basename='buyer_seller_order')
router.register('partner/orders', PartnerOrderView, basename='partner_orders')

urlpatterns = [
    path('', include('social_django.urls', namespace='social')),
    path('users/', UserViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'post': 'create'}), name='users'),
    path('users/auth/', AuthenticateView.as_view(), name='auth'),
    path('user/password_reset/', reset_password_request_token, name='password-reset'),
    path('user/password_reset/confirm/', CustomResetPasswordConfirm.as_view(), name='password-reset-confirm'),
    path('admin/', admin.site.urls),
    path('confirm_email/<str:temp_token>', ConfirmEmailView.as_view(), name='confirm_email'),
    path('partner/state/', PartnerStateView.as_view(), name='partner_state'),
    path('basket/', BasketView.as_view(), name='basket'),
] + router.urls
