from rest_framework import serializers

from public_discourse_sandbox.pds_app.models import Experiment
from public_discourse_sandbox.pds_app.models import Post
from public_discourse_sandbox.pds_app.models import UserProfile
from public_discourse_sandbox.pds_app.models import Vote


class UserProfileSerializer(serializers.ModelSerializer):
    is_verified = serializers.BooleanField(read_only=True)
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

class PostSerializer(serializers.ModelSerializer):
    author = UserProfileSerializer(source="user_profile", read_only=True)
    like_count = serializers.IntegerField(source="num_upvotes", read_only=True)
    repost_count = serializers.IntegerField(source="num_shares", read_only=True)
    hashtags = serializers.SerializerMethodField()
    liked_by_user = serializers.SerializerMethodField()
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    is_pinned = serializers.BooleanField(read_only=True)
    is_flagged = serializers.BooleanField(read_only=True)
    like_count = serializers.IntegerField(source="num_upvotes", read_only=True)
    reply_count = serializers.SerializerMethodField()
    repost_count = serializers.IntegerField(source="num_shares", read_only=True)
    class Meta:
        model = Post
        fields = [
            "id",
            "created_date",
            "last_modified",
            "content",
            "like_count",
            "num_downvotes",
            "num_comments",
            "repost_count",
            "hashtags",
            "author",
            "like_count",
            "reply_count",
            "repost_count",
            "liked_by_user",
            "is_deleted",
            "is_edited",
            "is_pinned",
            "is_flagged",
        ]
    def get_hashtags(self, obj):
        hashtags = obj.hashtag_set.all()
        return [{"tag": hashtag.tag} for hashtag in hashtags]

    def get_liked_by_user(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user_profile = request.user.userprofile_set.filter(
                experiment=obj.experiment,
            ).first()
            if user_profile:
                return Vote.objects.filter(
                    user_profile=user_profile,
                    post=obj,
                    is_upvote=True,
                ).exists()
        return False
    def get_reply_count(self, obj):
        return obj.get_comment_count()


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = [
            "id",
            "identifier",
            "name",
            "description",
            "created_date",
        ]
