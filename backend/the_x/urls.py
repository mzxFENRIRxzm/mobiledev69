from django.contrib import admin
from garage.auth_pages import TheXLoginView
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from garage.views import MotorcycleViewSet, me, sign_out
from garage.oidc import TheXProviderInfoView
from garage.bookings import BookingViewSet
from garage.shops import ShopViewSet

router = DefaultRouter()
router.register("shops", ShopViewSet, basename="shop")
router.register("motorcycles", MotorcycleViewSet, basename="motorcycle")
router.register("bookings", BookingViewSet, basename="booking")
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", TheXLoginView.as_view()),
    path("openid/.well-known/openid-configuration", TheXProviderInfoView.as_view()),
    path("openid/.well-known/openid-configuration/", TheXProviderInfoView.as_view()),
    path("openid/", include("oidc_provider.urls", namespace="oidc_provider")),
    path("api/me/", me),
    path("api/logout/", sign_out),
    path("api/", include(router.urls)),
]
