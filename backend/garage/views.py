from django.contrib.auth import logout
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from oidc_provider.models import Token
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Motorcycle, UserProfile
from .serializers import MotorcycleSerializer
from .roles import role_for


class MotorcycleViewSet(viewsets.ModelViewSet):
    serializer_class = MotorcycleSerializer

    def get_queryset(self):
        return Motorcycle.objects.filter(owner=self.request.user)

    def _save(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(owner=self.request.user)
        except IntegrityError:
            raise serializers.ValidationError({"license_plate": "ทะเบียนนี้มีในโรงรถของคุณแล้ว"})

    perform_create = _save
    perform_update = _save

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise serializers.ValidationError("รถคันนี้มีประวัติการจองซ่อม จึงไม่สามารถลบได้")


@api_view(["GET"])
def me(request):
    return Response({"id": request.user.pk, "username": request.user.username,
                     "role": role_for(request.user),
                     "phone": UserProfile.objects.filter(user=request.user).values_list('phone', flat=True).first() or ''})


@api_view(["POST"])
def sign_out(request):
    # Explicitly sign out all THE_X sessions belonging to this user.
    Token.objects.filter(user=request.user, client=request.auth.client).delete()
    logout(request)
    return Response(status=204)
