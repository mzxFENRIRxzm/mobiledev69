from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from smtplib import SMTPException
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import UserProfile
from .roles import role_for
from .email_accounts import send_verification_email


class ProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, allow_blank=True)
    last_name = serializers.CharField(max_length=150, allow_blank=True)
    email = serializers.EmailField(max_length=254, allow_blank=True)
    phone = serializers.RegexField(r'^\+?[0-9]{9,15}$', max_length=20,
        error_messages={'invalid': 'กรอกเบอร์โทร 9–15 หลัก เช่น 0812345678 หรือ +66812345678'})

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({'detail': 'แก้ไขได้เฉพาะชื่อ นามสกุล อีเมล และเบอร์โทร'})
        return super().to_internal_value(data)

    def validate_email(self, value):
        value = value.lower()
        if not value:
            return value
        if get_user_model().objects.filter(email__iexact=value).exclude(pk=self.context['user'].pk).exists():
            raise serializers.ValidationError('ไม่สามารถใช้อีเมลนี้ได้ กรุณาใช้อีเมลอื่น')
        if UserProfile.objects.filter(pending_email__iexact=value).exclude(user=self.context['user']).exists():
            raise serializers.ValidationError('ไม่สามารถใช้อีเมลนี้ได้ กรุณาใช้อีเมลอื่น')
        return value


def profile_data(user):
    profile = UserProfile.objects.filter(user=user).first()
    return {'username': user.username, 'role': role_for(user),
            'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email,
            'phone': profile.phone if profile else '',
            'pending_email': profile.pending_email if profile else '',
            'email_verified': bool(profile and profile.email_verified_at)}


@api_view(['GET', 'PATCH'])
def my_profile(request):
    verification_address = None
    if request.method == 'PATCH':
        try:
            with transaction.atomic():
                # Lock and reload so simultaneous edits to different fields are retained.
                user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                serializer = ProfileUpdateSerializer(data=request.data, partial=True, context={'user': user})
                serializer.is_valid(raise_exception=True)
                values = dict(serializer.validated_data)
                phone = values.pop('phone', None)
                requested_email = values.pop('email', None)
                for field, value in values.items():
                    setattr(user, field, value)
                if values:
                    user.save(update_fields=list(values))
                if phone is not None or requested_email is not None:
                    profile, _ = UserProfile.objects.select_for_update().get_or_create(
                        user=user, defaults={'phone': phone or ''})
                    changes = []
                    if phone is not None and profile.phone != phone:
                        profile.phone = phone
                        changes.append('phone')
                    if requested_email is not None:
                        if not requested_email and user.email:
                            user.email = ''
                            user.save(update_fields=['email'])
                            profile.email_verified_at = None
                            changes.append('email_verified_at')
                        pending = requested_email if requested_email != user.email else ''
                        if profile.pending_email != pending:
                            profile.pending_email = pending
                            changes.append('pending_email')
                            verification_address = pending or None
                    if changes:
                        profile.save(update_fields=changes)
        except IntegrityError as error:
            # The DB constraint also handles two accounts choosing the same email concurrently.
            if not any(name in str(error) for name in (
                    'the_x_user_email_unique', 'auth_user.email', 'the_x_pending_email_unique')):
                raise
            raise serializers.ValidationError({'email': 'ไม่สามารถใช้อีเมลนี้ได้ กรุณาใช้อีเมลอื่น'})
    else:
        user = request.user
    data = profile_data(user)
    if verification_address:
        try:
            send_verification_email(request, user, verification_address, 'change')
        except (OSError, SMTPException, UnicodeError):
            data['email_delivery_failed'] = True
    response = Response(data)
    response['Cache-Control'] = 'no-store'
    return response
