from django.urls import get_resolver
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from public_discourse_sandbox.pds_app.models import Post

from .serializers import PostSerializer


class HasAPIKey(BasePermission):
    def has_permission(self, request, view):
        api_key = request.headers.get("Authorization")
        return api_key == "key"


def extract_patterns(url_patterns, prefix=""):
    results = []
    for entry in url_patterns:
        if hasattr(entry, "url_patterns"):
            results += extract_patterns(entry.url_patterns, prefix + str(entry.pattern))
        else:
            results.append(prefix + str(entry.pattern))
    return results


@api_view(["GET"])
def list_routes(request):
    base_url = request.build_absolute_uri("/")
    resolver = get_resolver()
    all_patterns = extract_patterns(resolver.url_patterns)
    routes = [base_url + str(p) for p in all_patterns if p.startswith("public/api/")]
    return Response({"routes": routes})


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


@api_view(["GET"])
@permission_classes([HasAPIKey])
def get_posts(request):
    posts = Post.objects.all()
    paginator = CustomPagination()
    page = paginator.paginate_queryset(posts, request)
    serializer = PostSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
def post_detail(request, pk):
    try:
        post = Post.objects.get(pk=pk)
    except Post.DoesNotExist:
        return Response(
            {"error": "post does not exist"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        serializer = PostSerializer(post)
        return Response(serializer.data)
    return Response(status=status.HTTP_404_NOT_FOUND)
