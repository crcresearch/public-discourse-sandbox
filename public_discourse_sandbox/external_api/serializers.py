from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from rest_framework import serializers

from public_discourse_sandbox.pds_app.models import Post

"""
 "id": "7903138e-b34d-4e2c-922a-af8f5e9dcbcf",
        "created_date": "2025-08-12T13:01:38.656545-04:00",
        "last_modified": "2025-08-12T13:01:38.656555-04:00",
        "content": "hello world!!!",
        "depth": 0,
        "num_upvotes": 0,
        "num_downvotes": 0,
        "num_comments": 0,
        "num_shares": 0,
        "is_deleted": false,
        "is_edited": false,
        "is_pinned": false,
        "is_flagged": false,
        "user_profile": "006adb49-4e39-40ab-92be-57590d4c889e",
        "experiment": "58fa7aa8-c01d-4b3a-916c-12241fdada38",
        "parent_post": null,
        "repost_source": null
"""


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
