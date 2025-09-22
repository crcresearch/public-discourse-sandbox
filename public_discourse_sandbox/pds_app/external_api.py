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
from .serializers import ExperimentSerializer
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
            return Response({
                "error": "experiment does not exist",
            }, status=status.HTTP_404_NOT_FOUND)

        # check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return Response({
                "error": "user does not have access to this experiment",
                }, status=status.HTTP_403_FORBIDDEN)
        if user_profile.is_banned:
            return Response({
                "error": "user is banned from this experiment",
                }, status=status.HTTP_403_FORBIDDEN)
        page_size = min(int(request.query_params.get("page_size", 20)), 100)
        posts = list(get_home_feed_posts(
            request=request,
            experiment=experiment,
            page_size=page_size))
        paginator = CustomPagination()
        page = paginator.paginate_queryset(posts, request)
        serializer = PostSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        return Response({
            "error": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_get_post_by_id(request, pk, experiment_id):
    try:
        post = Post.objects.get(pk=pk)
        serializer = PostSerializer(post)
        return Response(serializer.data)
    except Post.DoesNotExist:
        return Response(
            {"error": "post does not exist"},
            status=status.HTTP_404_NOT_FOUND,
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
        return Response({
            "error": "user profile does not exist",
            }, status=status.HTTP_404_NOT_FOUND)
