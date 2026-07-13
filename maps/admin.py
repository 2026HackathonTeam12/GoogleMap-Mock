from django.contrib import admin

from .models import OwnerProfile, Review, ReviewReply


class ReviewReplyInline(admin.StackedInline):
    model = ReviewReply
    extra = 0
    max_num = 1


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
    readonly_fields = ('api_key', 'created_at', 'updated_at')


@admin.register(ReviewReply)
class ReviewReplyAdmin(admin.ModelAdmin):
    list_display = ('review', 'owner', 'created_at')
    search_fields = ('review__place_name', 'review__author_name', 'content', 'owner__username')
