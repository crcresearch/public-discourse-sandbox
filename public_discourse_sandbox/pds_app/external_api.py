# External API Endpoints
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Post
from .serializers import ExperimentSerializer
from .serializers import PostSerializer


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_home_timeline(request):
    """
    Get home timeline posts for the authenticated user.

    Query Parameters:
    - experiment_identifier: UUID of the experiment (required)
    - max_results: Number of posts to return (default: 20, max: 100)
    - since_id: Return posts after this ID
    - until_id: Return posts before this ID
    - pagination_token: Token for pagination
    """
    try:
        user_profile = request.user.userprofile_set.filter(is_banned=False).first()
        posts = Post.objects.filter(user_profile=user_profile)
        data = PostSerializer(posts, many=True)
        return Response({
            "data": data,
            }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            "error": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
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
