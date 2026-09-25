from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core.validators import RegexValidator
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from .models import UserProfile, Shop
from .uploads import clean_shop_photo


def validate_unique_email(value, exclude_pk=None):
    email = value.strip().lower()
    if email and get_user_model().objects.filter(email__iexact=email).exclude(pk=exclude_pk).exists():
        raise forms.ValidationError('ไม่สามารถใช้อีเมลนี้สมัครได้ กรุณาใช้อีเมลอื่น')
    if email and UserProfile.objects.filter(pending_email__iexact=email).exclude(user_id=exclude_pk).exists():
        raise forms.ValidationError('ไม่สามารถใช้อีเมลนี้สมัครได้ กรุณาใช้อีเมลอื่น')
    return email


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(label='อีเมล (ไม่บังคับ)', max_length=254, required=False,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    phone = forms.CharField(label='เบอร์โทรศัพท์', max_length=20,
        validators=[RegexValidator(r'^\+?[0-9]{9,15}$', 'กรอกเบอร์โทร 9–15 หลัก เช่น 0812345678 หรือ +66812345678')],
        widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}))
    account_type = forms.ChoiceField(label='ประเภทสมาชิก', initial='customer', choices=[
        ('customer', 'สมาชิกทั่วไป'), ('mechanic', 'ผู้ให้บริการซ่อมรถจักรยานยนต์')])
    shop_name = forms.CharField(label='ชื่อร้าน', max_length=160, required=False)
    shop_address = forms.CharField(label='ที่อยู่ร้าน', max_length=1000, required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'autocomplete': 'street-address'}))
    shop_photo = forms.FileField(label='รูปร้าน', required=False,
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='JPEG, PNG หรือ WebP ไม่เกิน 5 MB และ 16 ล้านพิกเซล')
    latitude = forms.DecimalField(label='ละติจูด', max_digits=9, decimal_places=6,
        min_value=-90, max_value=90, required=False, widget=forms.HiddenInput())
    longitude = forms.DecimalField(label='ลองจิจูด', max_digits=9, decimal_places=6,
        min_value=-180, max_value=180, required=False, widget=forms.HiddenInput())
    shop_fields = ('shop_name', 'shop_address', 'shop_photo', 'latitude', 'longitude')

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'autocomplete': 'username', 'autocapitalize': 'none'})
        for field in ('password1', 'password2'):
            self.fields[field].widget.attrs['autocomplete'] = 'new-password'

    def clean_email(self):
        return validate_unique_email(self.cleaned_data['email'])

    def clean_shop_photo(self):
        if self.data.get('account_type') != 'mechanic':
            return None
        return clean_shop_photo(self.cleaned_data.get('shop_photo'))

    def clean(self):
        data = super().clean()
        if data.get('account_type') == 'mechanic':
            for name in self.shop_fields:
                if name not in self.errors and data.get(name) in (None, ''):
                    self.add_error(name, 'กรุณาปักหมุดตำแหน่งร้านบนแผนที่' if name in ('latitude', 'longitude') else 'กรุณาระบุข้อมูลนี้สำหรับผู้ให้บริการ')
        return data

    def save(self, commit=True):
        if not commit:
            raise ValueError('Registration must save account, profile and shop together')
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        shop = None
        try:
            with transaction.atomic():
                user.save()
                UserProfile.objects.create(user=user, phone=self.cleaned_data['phone'],
                                           awaiting_signup_verification=False)
                if self.cleaned_data['account_type'] == 'mechanic':
                    group, _ = Group.objects.get_or_create(name='mechanics')
                    user.groups.add(group)
                    shop = Shop(name=self.cleaned_data['shop_name'], address=self.cleaned_data['shop_address'],
                        phone=self.cleaned_data['phone'], latitude=self.cleaned_data['latitude'],
                        longitude=self.cleaned_data['longitude'], photo=self.cleaned_data['shop_photo'],
                        accepting_bookings=True, awaiting_owner_verification=False)
                    shop.save()
                    shop.mechanics.add(user)
        except Exception:
            # Storage is not transactional; remove only this attempt's new file on rollback.
            if shop and shop.photo and shop.photo.name and shop.photo._committed:
                shop.photo.delete(save=False)
            raise
        return user


def safe_destination(request):
    destination = request.POST.get('next', '') if request.method == 'POST' else request.GET.get('next', '')
    if destination and url_has_allowed_host_and_scheme(destination,
            allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destination
    return ''


@sensitive_post_parameters('password1', 'password2')
@never_cache
@require_http_methods(['GET', 'POST'])
def register(request):
    if not settings.PUBLIC_SIGNUP_ENABLED:
        raise Http404
    destination = safe_destination(request)
    login_url = '/accounts/login/?' + urlencode({'next': destination})
    # An OIDC prompt=login can show the login page with an existing Django session.
    # Allow its signup link to open; creating a user must not replace that session.
    form = CustomerRegistrationForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            # Database uniqueness is authoritative if two valid forms race.
            form.add_error(None, 'ไม่สามารถใช้ชื่อผู้ใช้หรืออีเมลนี้ได้ กรุณาตรวจสอบและลองใหม่')
        except OSError:
            form.add_error(None, 'บันทึกรูปไม่สำเร็จ กรุณาเลือกรูปและลองใหม่')
        else:
            return HttpResponseRedirect(login_url + '&registered=1')
    response = render(request, 'registration/register.html', {
        'form': form, 'next': destination, 'login_url': login_url,
        'account_fields': [form[name] for name in ('username', 'email', 'phone', 'account_type', 'password1', 'password2')],
        'shop_fields': [form[name] for name in form.shop_fields],
    })
    response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
