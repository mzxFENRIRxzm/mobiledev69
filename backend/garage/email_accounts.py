"""Email ownership and password recovery for THE_X's Django OIDC provider."""
import hashlib
import logging
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import Shop, UserProfile


logger = logging.getLogger(__name__)
TOKEN_SALT = 'the-x-email-verification-v1'


def password_fingerprint(user):
    # Signed data is encoded, not encrypted. Never place the password hash in a URL.
    return salted_hmac(TOKEN_SALT, user.password).hexdigest()


def email_fingerprint(email):
    return salted_hmac(TOKEN_SALT + '-email', email.lower()).hexdigest()


def verification_token(user, email, purpose):
    return signing.dumps({'uid': user.pk, 'email': email_fingerprint(email),
                          'password': password_fingerprint(user),
                          'purpose': purpose}, salt=TOKEN_SALT)


def verification_target(token):
    try:
        data = signing.loads(token, salt=TOKEN_SALT,
                             max_age=settings.EMAIL_VERIFICATION_TIMEOUT)
        if data.get('purpose') not in ('signup', 'change'):
            return None
        user = get_user_model().objects.get(pk=data['uid'])
        if password_fingerprint(user) != data['password']:
            return None
        if data['purpose'] == 'signup':
            email = user.email
            profile = UserProfile.objects.get(user=user)
            if (user.is_active or not profile.awaiting_signup_verification or
                    email_fingerprint(email) != data['email']):
                return None
        else:
            profile = UserProfile.objects.get(user=user)
            email = profile.pending_email
            if not user.is_active or not email or email_fingerprint(email) != data['email']:
                return None
        return user, email, data['purpose']
    except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError,
            ValueError, get_user_model().DoesNotExist, UserProfile.DoesNotExist):
        return None


def send_verification_email(request, user, email=None, purpose='signup'):
    address = email or user.email
    token = verification_token(user, address, purpose)
    link = request.build_absolute_uri(reverse('verify-email', args=[token]))
    body = render_to_string('registration/verification_email.txt',
                            {'username': user.username, 'verification_url': link,
                             'hours': settings.EMAIL_VERIFICATION_TIMEOUT // 3600})
    delivered = send_mail('ยืนยันอีเมล THE_X', body, settings.DEFAULT_FROM_EMAIL,
                          [address], fail_silently=False)
    if delivered != 1:
        raise OSError('Verification email was not accepted by the backend')
    return link


class VerificationRequestForm(forms.Form):
    email = forms.EmailField(label='อีเมล', max_length=254,
                             widget=forms.EmailInput(attrs={'autocomplete': 'email'}))


@never_cache
@require_http_methods(['GET', 'POST'])
def resend_verification(request):
    form = VerificationRequestForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        address = form.cleaned_data['email'].strip().lower()
        # The same response for unknown, verified and pending addresses avoids
        # revealing which email belongs to an account.
        throttle_key = 'the-x-verification-' + hashlib.sha256(address.encode()).hexdigest()
        if cache.add(throttle_key, True, timeout=60):
            user = get_user_model().objects.filter(
                email__iexact=address, is_active=False,
                profile__awaiting_signup_verification=True).first()
            purpose = 'signup'
            if user is None:
                profile = (UserProfile.objects.select_related('user')
                           .filter(pending_email__iexact=address, user__is_active=True).first())
                user = profile.user if profile else None
                purpose = 'change'
            if user:
                try:
                    send_verification_email(request, user, address, purpose)
                except (OSError, SMTPException, UnicodeError):
                    cache.delete(throttle_key)
                    logger.exception('Could not send verification email')
        return render(request, 'registration/verification_sent.html', {})
    return render(request, 'registration/verification_resend.html', {'form': form})


@never_cache
@require_http_methods(['GET', 'POST'])
def verify_email(request, token):
    result_context = {'verified': False, 'frontend_login_url': settings.LOGIN_REDIRECT_URL}
    target = verification_target(token)
    if target is None:
        return render(request, 'registration/verification_result.html', result_context)
    if request.method == 'GET':
        return render(request, 'registration/verification_confirm.html', {'token': token})
    user, email, purpose = target
    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=user.pk)
            # Validate again under the lock to prevent accepting a changed email.
            if verification_target(token) is None:
                return render(request, 'registration/verification_result.html', result_context)
            profile = UserProfile.objects.select_for_update().get(user=user)
            if purpose == 'signup':
                user.is_active = True
                user.save(update_fields=['is_active'])
                profile.awaiting_signup_verification = False
                Shop.objects.filter(mechanics=user, awaiting_owner_verification=True).update(
                    awaiting_owner_verification=False, accepting_bookings=True)
            else:
                if get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    return render(request, 'registration/verification_result.html', result_context)
                user.email = email
                user.save(update_fields=['email'])
                profile.pending_email = ''
            profile.email_verified_at = timezone.now()
            profile.save(update_fields=['pending_email', 'email_verified_at',
                                        'awaiting_signup_verification'])
    except IntegrityError:
        return render(request, 'registration/verification_result.html', result_context)
    return render(request, 'registration/verification_result.html',
                  {'verified': True, 'frontend_login_url': settings.LOGIN_REDIRECT_URL})
