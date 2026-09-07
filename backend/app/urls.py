from .views import BookingListView
from django.urls import path

urlpatterns = [
    path('bookings/', BookingListView.as_view(), name='booking-list'),
]