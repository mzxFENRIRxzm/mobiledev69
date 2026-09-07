from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Booking

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'destination_name', 'start_date', 'end_date', 'price']
        # custom serializer สำหรับล็อกอินเพื่อส่งกลับ Custom Token Claims


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # เพิ่ม Custom Claim ลงใน Token
        token['name'] = user.username
        return token