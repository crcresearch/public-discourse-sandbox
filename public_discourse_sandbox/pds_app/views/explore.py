from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..models import Post

@login_required
def explore(request):
    """Explore page view."""
    # Fetch posts ordered by creation date, newest first
    posts = Post.objects.filter(
        is_deleted=False,
        parent_post__isnull=True  # Only show top-level posts, not replies
    ).select_related(
        'user_profile',
        'user_profile__user'
    ).order_by('-created_date')

    return render(request, 'pages/explore.html', {
        'posts': posts,
    }) 