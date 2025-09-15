from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes
from rest_framework.decorators import permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .authentication import BearerAuthentication
from .models import Post
from .serializers import ExperimentSerializer
from .serializers import PostSerializer


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

@api_view(["GET"])
@authentication_classes([BearerAuthentication])
@permission_classes([IsAuthenticated])
def api_home_timeline(request):
    try:
        user_profile = request.user.userprofile_set.filter(is_banned=False).first()
        posts = Post.objects.filter(user_profile=user_profile)
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
def api_get_post_by_id(request, pk):
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

        serializer = ExperimentSerializer(experiments, many=True)

        return Response({
            "data": serializer.data,
            }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            "error": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
