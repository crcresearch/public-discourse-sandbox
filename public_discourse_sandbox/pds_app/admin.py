from django.contrib import admin
from .models import Experiment, UserProfile, Post, Vote, SocialNetwork, DigitalTwin, Hashtag, Notification, ExperimentInvitation

@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ('name', 'creator', 'created_date', 'last_modified', 'is_deleted')
    search_fields = ('name', 'description')
    list_filter = ('creator', 'is_deleted')
    readonly_fields = ('created_date', 'last_modified')
    raw_id_fields = ('creator',)  # Uses a popup for better performance with many users

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'experiment', 'is_digital_twin', 'is_collaborator', 'is_moderator', 'is_banned', 'is_private', 'is_deleted', 'num_followers', 'num_following')
    search_fields = ('user__username', 'bio')
    list_filter = ('is_digital_twin', 'is_collaborator', 'is_moderator', 'is_banned', 'is_private', 'is_deleted', 'experiment')
    readonly_fields = ('created_date', 'last_modified', 'num_followers', 'num_following')
    raw_id_fields = ('user', 'experiment')
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'content_preview', 'depth', 'experiment', 'num_upvotes', 'num_downvotes', 'created_date', 'is_deleted', 'is_flagged')
    search_fields = ('content', 'user_profile__user__username')
    list_filter = ('is_deleted', 'is_edited', 'is_pinned', 'is_flagged', 'experiment', 'created_date')
    readonly_fields = ('created_date', 'last_modified', 'num_upvotes', 'num_downvotes', 'num_comments', 'num_shares')
    raw_id_fields = ('user_profile', 'experiment', 'parent_post')
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'
    
    # # Add a custom action to unflag posts
    # actions = ['unflag_posts']
    
    # def unflag_posts(self, request, queryset):
    #     updated = queryset.update(is_flagged=False)
    #     self.message_user(request, f"{updated} posts were successfully unflagged.")
    # unflag_posts.short_description = "Mark selected posts as not containing profanity"

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'post', 'is_upvote', 'created_date')
    list_filter = ('is_upvote', 'created_date')
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('created_date', 'last_modified')
    raw_id_fields = ('user_profile', 'post')
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)

@admin.register(SocialNetwork)
class SocialNetworkAdmin(admin.ModelAdmin):
    list_display = ('source_node', 'target_node', 'created_date')
    search_fields = ('source_node__user__username', 'target_node__user__username')
    readonly_fields = ('created_date', 'last_modified')
    raw_id_fields = ('source_node', 'target_node')
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)

@admin.register(DigitalTwin)
class DigitalTwinAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'is_active', 'last_post')
    search_fields = ('user_profile__user__username',)
    readonly_fields = ('created_date', 'last_modified', 'last_post')
    raw_id_fields = ('user_profile',)

@admin.register(Hashtag)
class HashtagAdmin(admin.ModelAdmin):
    list_display = ('tag', 'post', 'created_date')
    search_fields = ('tag', 'post__content')
    list_filter = ('created_date',)
    readonly_fields = ('created_date', 'last_modified')
    raw_id_fields = ('post',)
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'event', 'is_read', 'created_date')
    search_fields = ('user_profile__user__username', 'event', 'content')
    list_filter = ('is_read', 'event', 'created_date')
    readonly_fields = ('created_date', 'last_modified')
    raw_id_fields = ('user_profile',)
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)

@admin.register(ExperimentInvitation)
class ExperimentInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'experiment', 'created_by', 'created_date', 'is_deleted')
    search_fields = ('email', 'experiment__name')
    list_filter = ('is_deleted', 'created_date')
    readonly_fields = ('created_date', 'last_modified')
    raw_id_fields = ('experiment', 'created_by')
    date_hierarchy = 'created_date'
    ordering = ('-created_date',)