from rest_framework import serializers
from .models import Motorcycle


class MotorcycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Motorcycle
        fields = ["id", "brand", "model", "license_plate", "year", "mileage", "notes"]
        read_only_fields = ["id"]

    def validate_license_plate(self, value):
        value = value.strip().upper()
        existing = Motorcycle.objects.filter(owner=self.context["request"].user, license_plate=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("ทะเบียนนี้มีในโรงรถของคุณแล้ว")
        return value
