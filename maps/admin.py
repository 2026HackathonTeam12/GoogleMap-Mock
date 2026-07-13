from django.contrib import admin

from .models import OwnerAccessToken, OwnerAuthorizationCode, OwnerProfile, Review, ReviewReply


class ReviewReplyInline(admin.StackedInline):
    model = ReviewReply
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('place_name', 'author_name', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('place_id', 'place_name', 'author_name', 'content')
    inlines = [ReviewReplyInline]


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('place_name', 'user', 'place_id', 'created_at')
    search_fields = ('place_id', 'place_name', 'place_address', 'user__username')
    readonly_fields = ('client_id', 'client_secret', 'created_at', 'updated_at')


@admin.register(ReviewReply)
class ReviewReplyAdmin(admin.ModelAdmin):
    list_display = ('review', 'owner', 'created_at')
    search_fields = ('review__place_name', 'review__author_name', 'content', 'owner__username')


@admin.register(OwnerAccessToken)
class OwnerAccessTokenAdmin(admin.ModelAdmin):
    list_display = ('owner', 'expires_at', 'created_at')
    search_fields = ('owner__place_id', 'owner__place_name', 'token')
    readonly_fields = ('token', 'refresh_token', 'created_at')


@admin.register(OwnerAuthorizationCode)
class OwnerAuthorizationCodeAdmin(admin.ModelAdmin):
    list_display = ('owner', 'redirect_uri', 'expires_at', 'used_at', 'created_at')
    search_fields = ('owner__place_id', 'owner__place_name', 'code', 'redirect_uri')
    readonly_fields = ('code', 'created_at')
