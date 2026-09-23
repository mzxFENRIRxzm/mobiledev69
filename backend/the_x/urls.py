from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from garage.auth_pages import TheXLoginView
from django.contrib.auth.views import PasswordResetDoneView, PasswordResetCompleteView
from garage.email_accounts import (
    TheXPasswordResetView, TheXPasswordResetConfirmView,
    resend_verification, verify_email,
)
from garage.registration import register
from garage.geocoding import reverse_address, forward_address
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from garage.views import MotorcycleViewSet, me, sign_out
from garage.profiles import my_profile
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
    path("accounts/register/", register, name="register"),
    path("accounts/verify-email/<str:token>/", verify_email, name="verify-email"),
    path("accounts/resend-verification/", resend_verification, name="resend-verification"),
    path("accounts/password-reset/", TheXPasswordResetView.as_view(), name="password-reset"),
    path("accounts/password-reset/done/", PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'), name="password-reset-done"),
    path("accounts/password-reset/<uidb64>/<token>/", TheXPasswordResetConfirmView.as_view(),
         name="password-reset-confirm"),
    path("accounts/password-reset/complete/", PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'), name="password-reset-complete"),
    path("accounts/shop-address/", reverse_address, name="shop-address"),
    path("accounts/shop-geocode/", forward_address, name="shop-geocode"),
    path("openid/.well-known/openid-configuration", TheXProviderInfoView.as_view()),
    path("openid/.well-known/openid-configuration/", TheXProviderInfoView.as_view()),
    path("openid/", include("oidc_provider.urls", namespace="oidc_provider")),
    path("api/me/", me),
    path("api/profile/", my_profile),
    path("api/logout/", sign_out),
    path("api/", include(router.urls)),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
