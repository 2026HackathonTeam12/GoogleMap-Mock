import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def generate_owner_api_key():
    return f'okr_{secrets.token_urlsafe(32)}'


class OwnerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owner_profile',
    )
    place_id = models.CharField(max_length=255, unique=True)
    place_name = models.CharField(max_length=255)
    place_address = models.CharField(max_length=500, blank=True)
    api_key = models.CharField(max_length=128, unique=True, default=generate_owner_api_key)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['place_name']

    def __str__(self):
        return f'{self.place_name} - {self.user.get_username()}'

    def rotate_api_key(self):
        self.api_key = generate_owner_api_key()
        self.save(update_fields=['api_key', 'updated_at'])
        return self.api_key


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
