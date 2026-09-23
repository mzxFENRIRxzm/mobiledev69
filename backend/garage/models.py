from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from uuid import uuid4


def shop_photo_path(instance, filename):
    return f'shops/{uuid4().hex}.jpg'


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20)
    pending_email = models.EmailField(blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    awaiting_signup_verification = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(
            Lower('pending_email'), condition=~models.Q(pending_email=''),
            name='the_x_pending_email_unique',
        )]


class Motorcycle(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    license_plate = models.CharField(max_length=30)
    year = models.PositiveIntegerField(validators=[MinValueValidator(1900), MaxValueValidator(2100)])
    mileage = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["owner", "license_plate"], name="owner_plate_unique")]

    def __str__(self):
        return f"{self.brand} {self.model}"


class Shop(models.Model):
    name = models.CharField(max_length=160)
    address = models.TextField(max_length=1000)
    phone = models.CharField(max_length=30)
    description = models.TextField(max_length=2000, blank=True)
    photo = models.ImageField(upload_to=shop_photo_path, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])
    accepting_bookings = models.BooleanField(default=True)
    awaiting_owner_verification = models.BooleanField(default=False)
    mechanics = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="service_shops", blank=True,
        limit_choices_to={"groups__name": "mechanics"})

    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.CheckConstraint(condition=(
            models.Q(latitude__isnull=True, longitude__isnull=True) |
            models.Q(latitude__isnull=False, longitude__isnull=False,
                latitude__gte=-90, latitude__lte=90, longitude__gte=-180, longitude__lte=180)
        ), name='shop_coordinates_valid_pair')]

    def __str__(self):
        return self.name


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "รอรับงาน"
        ACCEPTED = "accepted", "รับงานแล้ว"
        IN_PROGRESS = "in_progress", "กำลังซ่อม"
        COMPLETED = "completed", "เสร็จแล้ว"
        CANCELLED = "cancelled", "ยกเลิกแล้ว"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    # Nullable only for phase-2 history. New API bookings require a shop.
    shop = models.ForeignKey(Shop, null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    shop_name = models.CharField(max_length=160, blank=True)
    cancellation_reason = models.TextField(max_length=1000, blank=True)
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.PROTECT, related_name="bookings")
    motorcycle_label = models.CharField(max_length=240)
    mechanic = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="repair_jobs")
    appointment_at = models.DateTimeField()
    problem = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    repair_notes = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["motorcycle"],
            condition=models.Q(status__in=["pending", "accepted", "in_progress"]),
            name="one_active_booking_per_motorcycle")]


class BookingEvent(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Booking.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
