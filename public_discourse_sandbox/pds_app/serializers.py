from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Experiment
from .models import Hashtag
from .models import Post
from .models import UserProfile

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    profile_picture = serializers.ImageField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    is_banned = serializers.BooleanField(read_only=True)
    created_date = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "display_name",
            "profile_picture",
            "is_verified",
            "is_banned",
            "created_date",
        ]


class HashTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ["tag"]


class PostSerializer(serializers.ModelSerializer):
    author = UserProfileSerializer(source="user_profile", read_only=True)
    text = serializers.CharField(source="content", read_only=True)
    # created_at = serializers.DateTimeField(source="created_date", read_only=True)
    # updated_at = serializers.DateTimeField(source="updated_date", read_only=True)
    #
    # like_count = serializers.IntegerField(source="num_upvotes", read_only=True)
    # reply_count = serializers.SerializerMethodField()
    # repost_count = serializers.IntegerField(source="num_shares", read_only=True)
    #
    # is_deleted = serializers.BooleanField(read_only=True)
    # is_edited = serializers.BooleanField(read_only=True)
    # is_pinned = serializers.BooleanField(read_only=True)
    # is_flagged = serializers.BooleanField(read_only=True)
    #
    # in_reply_to_id = serializers.UUIDField(source="parent_post.id", read_only=True)
    # repost_source_id = serializers.UUIDField(source="repost_source.id", read_only=True)
    #
    # hashtags = serializers.SerializerMethodField()
    #
    # liked_by_user = serializers.SerializerMethodField()
    #
    # class Meta:
    #     model = Post
    #     fields = [
    #         "id",
    #         "text",
    #         "author",
    #         "created_at",
    #         "updated_at",
    #         "like_count",
    #         "reply_count",
    #         "repost_count",
    #         "is_deleted",
    #         "is_edited",
    #         "is_pinned",
    #         "is_flagged",
    #         "in_reply_to_id",
    #         "repost_source_id",
    #         "hashtags",
    #         "liked_by_user",
    #     ]
    #
    # def get_reply_count(self, obj):
    #     return obj.get_comment_count()
    #
    # def get_hashtags(self, obj):
    #     hashtags = obj.hashtag_set.all()
    #     return [{"tag": hashtag.tag} for hashtag in hashtags]
    #
    # def get_liked_by_user(self, obj):
    #     request = self.context.get("request")
    #     if request and request.user.is_authenticated:
    #         user_profile = request.user.userprofile_set.filter(
    #             experiment=obj.experiment,
    #         )
    #         if user_profile:
    #             return Vote.objects.filter(
    #                 user_profile=user_profile, post=obj, is_upvote=True,
    #             ).exists()
    #     return False


class PostCreateSerializer(serializers.ModelSerializer):
    text = serializers.CharField(source="content", max_length=500)

    class Meta:
        model = Post
        fields = ["text"]

    def create(self, validated_data):
        request = self.context.get("request")
        experiment = self.context.get("experiment")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication request")

        if not experiment:
            raise serializers.ValidationError("Experiment context required")

        user_profile = request.user.userprofile_set.filter(
            experiment=experiment,
        ).first()

        if not user_profile:
            raise serializers.ValidationError(
                "User profile not found for this experiment",
            )

        if user_profile.is_banned:
            raise serializers.ValidationError("User is banned from this experiment")

        post = Post.objects.create(
            user_profile=user_profile,
            experiment=experiment,
            content=validated_data["content"],
            depth=0,
            parent_post=None,
        )

        return post


class PostReplySerializer(serializers.ModelSerializer):
    text = serializers.CharField(source="content", max_length=500)
    in_reply_to_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Post
        fields = ["text", "in_reply_to_id"]

    def create(self, validated_data):
        request = self.context.get("request")
        experiment = self.context.get("experiment")
        parent_post_id = validated_data.pop("in_reply_to_id")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        if not experiment:
            raise serializers.ValidationError("Experiment context required")

        user_profile = request.user.userprofile_set.filter(
            experiment=experiment,
        ).first()

        if not user_profile:
            raise serializers.ValidationError(
                "User profile not found for this experiment",
            )

        if user_profile.is_banned:
            raise serializers.ValidationError("User is banned from this experiment")

        try:
            parent_post = Post.objects.get(id=parent_post_id, experiment=experiment)
        except Post.DoesNotExist:
            raise serializers.ValidationError("Parent post not found")

        return Post.objects.create(
            user_profile=user_profile,
            experiment=experiment,
            content=validated_data["content"],
            parent_post=parent_post,
            depth=parent_post.depth + 1,
        )


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = [
            "id",
            "identifier",
            "name",
            "description",
            "created_date",
            "is_deleted",
        ]
