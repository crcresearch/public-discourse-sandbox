from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes
from rest_framework.decorators import permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .authentication import BearerAuthentication
from .models import Experiment
from .models import Post
from .models import UserProfile
from .models import Vote
from .serializers import ExperimentSerializer
from .serializers import PostCreateSerializer
from .serializers import PostReplySerializer
from .serializers import PostSerializer
from .views import get_home_feed_posts


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


@api_view(["GET"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_home_timeline(request, experiment_id):
    try:
        try:
            experiment = Experiment.objects.get(identifier=experiment_id)
        except Experiment.DoesNotExist:
            return Response(
                {
                    "error": "experiment does not exist",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(
            experiment=experiment
        ).first()
        if not user_profile:
            return Response(
                {
                    "error": "user does not have access to this experiment",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if user_profile.is_banned:
            return Response(
                {
                    "error": "user is banned from this experiment",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        page_size = min(int(request.query_params.get("page_size", 20)), 100)
        posts = list(
            get_home_feed_posts(
                request=request, experiment=experiment, page_size=page_size
            )
        )
        paginator = CustomPagination()
        page = paginator.paginate_queryset(posts, request)
        serializer = PostSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        return Response(
            {
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_user_experiments(request):
    try:
        user_profiles = request.user.userprofile_set.filter(is_banned=False)
        experiments = [profile.experiment for profile in user_profiles]
        paginator = CustomPagination()
        page = paginator.paginate_queryset(experiments, request)
        serializer = ExperimentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    except UserProfile.DoesNotExist:
        return Response(
            {
                "error": "user experiments do not exist",
            },
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_search_posts(request, experiment_id):
    query = request.query_params.get("query")
    if not query:
        return Response(
            {
                "error": "query parameter is required",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        experiment = Experiment.objects.get(identifier=experiment_id)
    except Experiment.DoesNotExist:
        return Response(
            {
                "error": "experiment does not exist",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
    if not user_profile:
        return Response(
            {
                "error": "User does not have access to this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if user_profile.is_banned:
        return Response(
            {
                "error": "user is banned from this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    from django.db import models

    max_results = min(int(request.query_params.get("page_size", 10)), 100)
    posts = (
        Post.objects.filter(
            experiment=experiment, is_deleted=False, parent_post__isnull=True
        )
        .filter(
            models.Q(content__icontains=query)
            | models.Q(hashtag__tag__icontains=query.lower()),
        )
        .select_related(
            "user_profile",
            "user_profile__user",
        )
        .prefetch_related(
            "vote_set",
            "hashtag_set",
        )
        .order_by("-created_date")
    )
    for post in posts:
        post.comment_count = post.get_comment_count()
        post.user_has_voted = Vote.objects.filter(
            user_profile=user_profile,
            post=post,
            is_upvote=True,
        ).exists()
    paginator = CustomPagination()
    page = paginator.paginate_queryset(posts, request)
    serializer = PostSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_get_post_by_id(request, post_id):
    try:
        post = Post.objects.get(id=post_id, is_deleted=False)
    except Post.DoesNotExist:
        return Response(
            {
                "error": "Post not found",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # check if user have access to the experiment
    user_profile = request.user.userprofile_set.filter(
        experiment=post.experiment
    ).first()
    if not user_profile:
        return Response(
            {
                "error": "user does not have access to this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if user_profile.is_banned:
        return Response(
            {
                "error": "User is banned from this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    post.comment_count = post.get_comment_count()
    post.user_has_voted = Vote.objects.filter(
        user_profile=user_profile,
        post=post,
        is_upvote=True,
    ).exists()
    serializer = PostSerializer(post)
    return Response(
        {
            "data": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_create_post(request, experiment_id):
    try:
        experiment = Experiment.objects.get(identifier=experiment_id)
    except Experiment.DoesNotExist:
        return Response(
            {
                "error": "experiment does not exist",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # check if user has access to this experiment
    user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
    if not user_profile:
        return Response(
            {
                "error": "user does not have access to this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    if user_profile.is_banned:
        return Response(
            {
                "error": "user is banned from this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = PostCreateSerializer(
        data=request.data,
        context={"request": request, "experiment": experiment},
    )

    if serializer.is_valid():
        post = serializer.save()

        response_serializer = PostSerializer(post)
        return Response(
            {
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(
        {
            "error": "invalid data",
            "details": serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_like_post(request, post_id):
    try:
        post = Post.objects.get(id=post_id, is_deleted=False)
    except Post.DoesNotExist:
        return Response(
            {
                "error": "post not found",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    user_profile = request.user.userprofile_set.filter(
        experiment=post.experiment
    ).first()
    if not user_profile:
        return Response(
            {
                "error": "user does not have access to this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if user_profile.is_banned:
        return Response(
            {
                "error": "user is banned from this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    existing_vote = Vote.objects.filter(user_profile=user_profile, post=post).first()
    if existing_vote:
        existing_vote.delete()
        post.num_upvotes -= 1
        post.save()
        like = False
    else:
        Vote.objects.create(
            user_profile=user_profile,
            post=post,
            is_upvote=True,
        )
        post.num_upvotes += 1
        post.save()
        like = True
    return Response(
        {
            "data": {
                "liked": like,
                "like_count": post.num_upvotes,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_create_comment(request, post_id):
    try:
        parent_post = Post.objects.get(id=post_id, is_deleted=False)
    except Post.DoesNotExist:
        return Response(
            {
                "error": "post not found",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    user_profile = request.user.userprofile_set.filter(
        experiment=parent_post.experiment
    ).first()
    if not user_profile:
        return Response(
            {
                "error": "user does not have access to this experiment",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    comment_data = request.data.copy()
    comment_data["in_reply_to_id"] = str(parent_post.id)

    serializer = PostReplySerializer(
        data=comment_data,
        context={"request": request, "experiment": parent_post.experiment},
    )

    if serializer.is_valid():
        comment = serializer.save()

        response_serializer = PostSerializer(comment, context={"request": request})
        return Response(
            {
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(
        {
            "error": "invalid data",
            "details": serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
