from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from .models import Shop
from .bookings import is_mechanic


class ShopSerializer(serializers.ModelSerializer):
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "name", "address", "phone", "description", "accepting_bookings", "can_manage"]

    def get_can_manage(self, shop):
        user = self.context["request"].user
        return user.is_superuser or (is_mechanic(user) and shop.mechanics.filter(pk=user.pk).exists())


class ShopViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        if not serializer.get_can_manage(serializer.instance):
            raise PermissionDenied("แก้ไขได้เฉพาะร้านที่คุณเป็นสมาชิก")
        serializer.save()
