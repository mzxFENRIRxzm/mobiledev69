from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from garage.auth_pages import TheXLoginView
from garage.email_accounts import (
    resend_verification, verify_email,
)
from garage.username_reset import username_password_reset
from garage.registration import register
from garage.geocoding import reverse_address, forward_address
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from garage.views import MotorcycleViewSet, me, sign_out
from garage.profiles import my_profile
from garage.oidc import TheXProviderInfoView
from garage.bookings import BookingViewSet
from garage.shops import ShopViewSet
from garage.chat import ConversationViewSet
from garage.notifications import NotificationViewSet
from garage.ai_chat import ai_chat, ai_conversations, ai_conversation
from garage import admin_api
from garage import admin_database
from garage import admin_vectors

router = DefaultRouter()
router.register("shops", ShopViewSet, basename="shop")
router.register("motorcycles", MotorcycleViewSet, basename="motorcycle")
router.register("bookings", BookingViewSet, basename="booking")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("notifications", NotificationViewSet, basename="notification")
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", TheXLoginView.as_view()),
    path("accounts/register/", register, name="register"),
    path("accounts/verify-email/<str:token>/", verify_email, name="verify-email"),
    path("accounts/resend-verification/", resend_verification, name="resend-verification"),
    path("accounts/password-reset/", username_password_reset, name="password-reset"),
    path("accounts/shop-address/", reverse_address, name="shop-address"),
    path("accounts/shop-geocode/", forward_address, name="shop-geocode"),
    path("openid/.well-known/openid-configuration", TheXProviderInfoView.as_view()),
    path("openid/.well-known/openid-configuration/", TheXProviderInfoView.as_view()),
    path("openid/", include("oidc_provider.urls", namespace="oidc_provider")),
    path("api/me/", me),
    path("api/admin/overview/", admin_api.admin_overview),
    path("api/admin/users/", admin_api.admin_users),
    path("api/admin/audit/", admin_api.admin_audit),
    path("api/admin/users/<int:pk>/", admin_api.admin_user),
    path("api/admin/users/<int:pk>/motorcycles/", admin_api.admin_user_motorcycles),
    path("api/admin/users/<int:pk>/motorcycles/<int:motorcycle_pk>/", admin_api.admin_user_motorcycle),
    path("api/admin/users/<int:pk>/motorcycles/<int:motorcycle_pk>/archive/", admin_api.admin_user_motorcycle_archive),
    path("api/admin/shops/", admin_api.admin_shops),
    path("api/admin/mechanics/", admin_api.admin_mechanics),
    path("api/admin/shops/<int:pk>/", admin_api.admin_shop),
    path("api/admin/shops/<int:pk>/details/", admin_api.admin_shop_details),
    path("api/admin/shops/<int:pk>/moderate/", admin_api.admin_shop_moderate),
    path("api/admin/bookings/", admin_api.admin_bookings),
    path("api/admin/bookings/<int:pk>/", admin_api.admin_booking_detail),
    path("api/admin/bookings/<int:pk>/action/", admin_api.admin_booking_action),
    path("api/admin/database/", admin_database.admin_database_tables),
    path("api/admin/database/<str:table>/", admin_database.admin_database_rows),
    path("api/admin/database/<str:table>/<str:pk>/action/", admin_database.admin_database_action),
    path("api/admin/database/<str:table>/<str:pk>/", admin_database.admin_database_edit),
    path("api/admin/knowledge/", admin_api.admin_knowledge),
    path("api/admin/knowledge/<int:pk>/", admin_api.admin_knowledge_item),
    path("api/admin/knowledge/<int:pk>/embed/", admin_api.admin_embed_knowledge),
    path("api/admin/ai-vectors/", admin_vectors.admin_vectors),
    path("api/admin/ai-vectors/<uuid:pk>/", admin_vectors.admin_vector_item),
    path("api/admin/embedding-key/", admin_api.admin_embedding_key),
    path("api/profile/", my_profile),
    path("api/logout/", sign_out),
    path("api/ai-chat/", ai_chat),
    path("api/ai-conversations/", ai_conversations),
    path("api/ai-conversations/<uuid:pk>/", ai_conversation),
    path("api/", include(router.urls)),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
