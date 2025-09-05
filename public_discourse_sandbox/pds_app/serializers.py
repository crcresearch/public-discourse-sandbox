"""
Serializers for the Public Discourse Sandbox API.
Provides structured data serialization for external API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Post, UserProfile, Experiment, Vote, Notification, Hashtag

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile model.
    Provides user profile information for API responses.
    """
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    profile_picture = serializers.ImageField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    is_banned = serializers.BooleanField(read_only=True)
    created_date = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'display_name', 'profile_picture', 
            'is_verified', 'is_banned', 'created_date'
        ]


class HashtagSerializer(serializers.ModelSerializer):
    """
    Serializer for Hashtag model.
    Provides hashtag information for posts.
    """
    class Meta:
        model = Hashtag
        fields = ['tag']


class PostSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for Post model.
    Provides detailed post information similar to X's API structure.
    """
    # User information
    author = UserProfileSerializer(source='user_profile', read_only=True)

    # Post content and metadata
    text = serializers.CharField(source='content', read_only=True)
    created_at = serializers.DateTimeField(source='created_date', read_only=True)
    updated_at = serializers.DateTimeField(source='last_modified', read_only=True)

    # Engagement metrics
    like_count = serializers.IntegerField(source='num_upvotes', read_only=True)
    reply_count = serializers.SerializerMethodField()
    repost_count = serializers.IntegerField(source='num_shares', read_only=True)

    # Post status
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    is_pinned = serializers.BooleanField(read_only=True)
    is_flagged = serializers.BooleanField(read_only=True)

    # Relationships
    in_reply_to_id = serializers.UUIDField(source='parent_post.id', read_only=True)
    repost_source_id = serializers.UUIDField(source='repost_source.id', read_only=True)

    # Hashtags
    hashtags = serializers.SerializerMethodField()

    # User interaction status (requires request context)
    liked_by_user = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'text', 'author', 'created_at', 'updated_at',
            'like_count', 'reply_count', 'repost_count',
            'is_deleted', 'is_edited', 'is_pinned', 'is_flagged',
            'in_reply_to_id', 'repost_source_id', 'hashtags',
            'liked_by_user'
        ]

    def get_reply_count(self, obj):
        """Get the number of replies to this post."""
        return obj.get_comment_count()

    def get_hashtags(self, obj):
        """Get hashtags associated with this post."""
        hashtags = obj.hashtag_set.all()
        return [{'tag': hashtag.tag} for hashtag in hashtags]

    def get_liked_by_user(self, obj):
        """Check if the current user has liked this post."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Get user profile for the experiment
            user_profile = request.user.userprofile_set.filter(
                experiment=obj.experiment
            ).first()
            if user_profile:
                return Vote.objects.filter(
                    user_profile=user_profile,
                    post=obj,
                    is_upvote=True
                ).exists()
        return False


class PostCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new posts via API.
    """
    text = serializers.CharField(source='content', max_length=500)

    class Meta:
        model = Post
        fields = ['text']

    def create(self, validated_data):
        """Create a new post with the current user's profile."""
        request = self.context.get('request')
        experiment = self.context.get('experiment')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        if not experiment:
            raise serializers.ValidationError("Experiment context required")

        # Get user profile for the experiment
        user_profile = request.user.userprofile_set.filter(
            experiment=experiment
        ).first()

        if not user_profile:
            raise serializers.ValidationError("User profile not found for this experiment")

        if user_profile.is_banned:
            raise serializers.ValidationError("User is banned from this experiment")

        # Create the post
        post = Post.objects.create(
            user_profile=user_profile,
            experiment=experiment,
            content=validated_data['content'],
            depth=0,
            parent_post=None
        )

        return post


class PostReplySerializer(serializers.ModelSerializer):
    """
    Serializer for creating replies to posts via API.
    """
    text = serializers.CharField(source='content', max_length=500)
    in_reply_to_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Post
        fields = ['text', 'in_reply_to_id']

    def create(self, validated_data):
        """Create a reply to an existing post."""
        request = self.context.get('request')
        experiment = self.context.get('experiment')
        parent_post_id = validated_data.pop('in_reply_to_id')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        if not experiment:
            raise serializers.ValidationError("Experiment context required")

        # Get user profile for the experiment
        user_profile = request.user.userprofile_set.filter(
            experiment=experiment
        ).first()

        if not user_profile:
            raise serializers.ValidationError("User profile not found for this experiment")

        if user_profile.is_banned:
            raise serializers.ValidationError("User is banned from this experiment")

        # Get parent post
        try:
            parent_post = Post.objects.get(id=parent_post_id, experiment=experiment)
        except Post.DoesNotExist:
            raise serializers.ValidationError("Parent post not found")

        # Create the reply
        reply = Post.objects.create(
            user_profile=user_profile,
            experiment=experiment,
            content=validated_data['content'],
            parent_post=parent_post,
            depth=parent_post.depth + 1
        )

        return reply


class ExperimentSerializer(serializers.ModelSerializer):
    """
    Serializer for Experiment model.
    Provides experiment information for API responses.
    """
    class Meta:
        model = Experiment
        fields = [
            'id', 'identifier', 'name', 'description', 
            'created_date', 'is_deleted'
        ]