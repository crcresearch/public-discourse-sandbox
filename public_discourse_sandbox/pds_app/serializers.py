from rest_framework import serializers

from public_discourse_sandbox.pds_app.models import Experiment
from public_discourse_sandbox.pds_app.models import Post
from public_discourse_sandbox.pds_app.models import UserProfile
from public_discourse_sandbox.pds_app.models import Vote


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "display_name",
            "profile_picture",
            # "is_verified",
            "is_banned",
            "created_date",
        ]

class PostSerializer(serializers.ModelSerializer):

    author = UserProfileSerializer(source="user_profile", read_only=True)
    like_count = serializers.IntegerField(source="num_upvotes", read_only=True)
    repost_count = serializers.IntegerField(source="num_shares", read_only=True)
    hashtags = serializers.SerializerMethodField()
    liked_by_user = serializers.SerializerMethodField()
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
            "liked_by_user",
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
