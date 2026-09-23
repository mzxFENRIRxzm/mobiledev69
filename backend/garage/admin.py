from django.contrib import admin
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from .roles import RoleChangeForm, RoleCreationForm
from .models import Motorcycle, Shop, Booking, BookingEvent, UserProfile
from .uploads import clean_shop_photo

admin.site.unregister(get_user_model())
admin.site.site_header = "THE_X · จัดการระบบ"
admin.site.site_title = "THE_X Admin"
admin.site.index_title = "ผู้ใช้ โรงรถ ร้านบริการ และงานซ่อม"


class RoleFilter(admin.SimpleListFilter):
    title = "บทบาท THE_X"
    parameter_name = "role"

    def lookups(self, request, model_admin):
        return RoleChangeForm.base_fields["role"].choices

    def queryset(self, request, queryset):
        if self.value() == "admin":
            return queryset.filter(is_superuser=True)
        if self.value() == "mechanic":
            return queryset.filter(is_superuser=False, groups__name="mechanics").distinct()
        if self.value() == "customer":
            return queryset.filter(is_superuser=False).exclude(groups__name="mechanics")
        return queryset


@admin.register(get_user_model())
class TheXUserAdmin(UserAdmin):
    readonly_fields = ('contact_phone',)
    form = RoleChangeForm
    add_form = RoleCreationForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("ข้อมูลผู้ใช้", {"fields": ("first_name", "last_name", "email", "contact_phone")}),
        ("สิทธิ์ THE_X", {"fields": ("role", "is_active"),
         "description": "Adminuser มีสิทธิ์ดูแลระบบทั้งหมด; Mechanicuser ต้องกำหนดร้านใน Shops ด้วย"}),
    )
    add_fieldsets = ((None, {"fields": ("username", "password1", "password2", "role")}),)
    filter_horizontal = ()
    list_display = ("username", "email", "first_name", "last_name", "the_x_role", "is_active", "date_joined")
    list_filter = (RoleFilter, "is_active", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    list_per_page = 30

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("groups").select_related('profile')

    @admin.display(description='เบอร์โทรศัพท์')
    def contact_phone(self, obj):
        return obj.profile.phone if hasattr(obj, 'profile') else '—'

    @admin.display(description="บทบาท THE_X")
    def the_x_role(self, obj):
        role = "admin" if obj.is_superuser else (
            "mechanic" if any(group.name == "mechanics" for group in obj.groups.all()) else "customer")
        return dict(RoleChangeForm.base_fields["role"].choices)[role]

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission

    def has_delete_permission(self, request, obj=None):
        # Preserve ownership/history and prevent deletion of the last admin.
        return False

@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = ("license_plate", "brand", "model", "year", "mileage", "owner")
    list_filter = ("brand", "year")
    search_fields = ("license_plate", "brand", "model", "owner__username")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    list_per_page = 30
    fieldsets = (
        ("รถและเจ้าของ", {"fields": ("owner", "brand", "model", "license_plate", "year")}),
        ("การใช้งาน", {"fields": ("mileage", "notes", "created_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        return ("created_at", "owner") if obj else ("created_at",)

class ShopAdminForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = '__all__'

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        return clean_shop_photo(photo) if 'photo' in self.files else photo


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    form = ShopAdminForm
    list_display = ["name", "phone", "accepting_bookings", "mechanic_count"]
    list_filter = ("accepting_bookings",)
    search_fields = ("name", "address", "phone", "mechanics__username")
    filter_horizontal = ["mechanics"]
    list_per_page = 30
    fieldsets = (
        ("ข้อมูลร้าน", {"fields": ("name", "address", "phone", "description", "photo", "latitude", "longitude")}),
        ("การรับงานและสมาชิก", {"fields": ("accepting_bookings", "mechanics")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(member_count=Count("mechanics", distinct=True))

    @admin.display(description="จำนวนช่าง", ordering="member_count")
    def mechanic_count(self, obj):
        return obj.member_count


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    fields = ("status", "actor", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    ordering = ("created_at", "pk")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("actor")

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "shop", "customer", "motorcycle_label", "mechanic", "status", "appointment_at"]
    list_filter = ("status", ("shop", admin.RelatedOnlyFieldListFilter), "appointment_at")
    search_fields = ("=id", "customer__username", "mechanic__username", "motorcycle_label", "shop_name", "problem")
    date_hierarchy = "appointment_at"
    list_select_related = ("shop", "customer", "mechanic")
    list_per_page = 30
    readonly_fields = [field.name for field in Booking._meta.fields]
    fieldsets = (
        ("ข้อมูลการจอง", {"fields": ("id", "customer", "shop", "shop_name", "motorcycle", "motorcycle_label", "appointment_at", "problem")}),
        ("ผลการดำเนินงาน", {"fields": ("mechanic", "status", "repair_notes", "cancellation_reason"),
         "description": "ดูประวัติได้ที่นี่ การรับงาน/เปลี่ยนสถานะให้ใช้ขั้นตอนในแอป THE_X"}),
        ("เวลาในระบบ", {"fields": ("created_at", "updated_at")}),
    )
    inlines = (BookingEventInline,)
    def has_change_permission(self, request, obj=None):
        return False
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(BookingEvent)
class BookingEventAdmin(admin.ModelAdmin):
    list_display = ("booking", "status", "actor", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("=booking__id", "actor__username", "booking__motorcycle_label")
    list_select_related = ("booking", "actor")
    date_hierarchy = "created_at"
    list_per_page = 50
    readonly_fields = [field.name for field in BookingEvent._meta.fields]
    def has_change_permission(self, request, obj=None):
        return False
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
