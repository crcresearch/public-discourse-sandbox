from rest_framework import serializers

from public_discourse_sandbox.pds_app.models import Experiment
from public_discourse_sandbox.pds_app.models import Post


class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = [
            "id",
            "created_date",
            "last_modified",
            "content",
            "num_upvotes",
            "num_downvotes",
            "num_comments",
            "num_shares",
            "user_profile",
        ]


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
