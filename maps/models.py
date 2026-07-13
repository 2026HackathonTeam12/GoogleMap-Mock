import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def generate_owner_client_id():
    return f'oci_{secrets.token_urlsafe(18)}'


def generate_owner_client_secret():
    return f'ocs_{secrets.token_urlsafe(32)}'


def generate_owner_api_key():
    return generate_owner_client_secret()


def generate_owner_access_token():
    return f'oat_{secrets.token_urlsafe(40)}'


def generate_owner_refresh_token():
    return f'ort_{secrets.token_urlsafe(48)}'


def generate_owner_authorization_code():
    return f'oac_{secrets.token_urlsafe(32)}'


def default_token_expires_at():
    return timezone.now() + timedelta(minutes=15)


def default_refresh_expires_at():
    return timezone.now() + timedelta(days=30)


def default_authorization_code_expires_at():
    return timezone.now() + timedelta(minutes=5)


class OwnerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owner_profile',
    )
    place_id = models.CharField(max_length=255, unique=True)
    place_name = models.CharField(max_length=255)
    place_address = models.CharField(max_length=500, blank=True)
    client_id = models.CharField(max_length=128, unique=True, default=generate_owner_client_id)
    client_secret = models.CharField(max_length=128, unique=True, default=generate_owner_client_secret)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['place_name']

    def __str__(self):
        return f'{self.place_name} - {self.user.get_username()}'

    def rotate_client_credentials(self):
        self.client_id = generate_owner_client_id()
        self.client_secret = generate_owner_client_secret()
        self.oauth_tokens.all().delete()
        self.oauth_codes.all().delete()
        self.save(update_fields=['client_id', 'client_secret', 'updated_at'])
        return self.client_id, self.client_secret


class OwnerAuthorizationCode(models.Model):
    owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.CASCADE,
        related_name='oauth_codes',
    )
    code = models.CharField(max_length=160, unique=True, default=generate_owner_authorization_code)
    redirect_uri = models.URLField(max_length=500)
    state = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(default=default_authorization_code_expires_at)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'OAuth code for {self.owner}'

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_used(self):
        return bool(self.used_at)


class OwnerAccessToken(models.Model):
    owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.CASCADE,
        related_name='oauth_tokens',
    )
    token = models.CharField(max_length=160, unique=True, default=generate_owner_access_token)
    refresh_token = models.CharField(max_length=180, unique=True, default=generate_owner_refresh_token)
    expires_at = models.DateTimeField(default=default_token_expires_at)
    refresh_expires_at = models.DateTimeField(default=default_refresh_expires_at)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['refresh_token']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['refresh_expires_at']),
        ]

    def __str__(self):
        return f'OAuth token for {self.owner}'

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_refresh_expired(self):
        return self.refresh_expires_at <= timezone.now()

    @property
    def is_revoked(self):
        return bool(self.revoked_at)


class Review(models.Model):
    place_id = models.CharField(max_length=255, db_index=True)
    place_name = models.CharField(max_length=255)
    author_name = models.CharField(max_length=80)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    content = models.TextField(max_length=2000)
    delete_password_hash = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['place_id', '-created_at']),
        ]

    def __str__(self):
        return f'{self.place_name} - {self.author_name}'

    def set_delete_password(self, raw_password):
        self.delete_password_hash = make_password(raw_password)

    def check_delete_password(self, raw_password):
        return bool(self.delete_password_hash and check_password(raw_password, self.delete_password_hash))


class ReviewReply(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='replies',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='review_replies',
    )
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Reply to review #{self.review_id}'
