from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.db.models import Count, Q, Subquery, OuterRef
from .forms import PostForm
from .models import Post
from django.db import models
from django.http import JsonResponse

def get_active_posts():
    """Get non-deleted top-level posts with related user data."""
    return Post.objects.filter(
        parent_post__isnull=True  # Only show top-level posts, not replies
    ).select_related(
        'user_profile',
        'user_profile__user'
    ).annotate(
        comment_count=Count('post')
    ).order_by('-created_date')

class HomeView(LoginRequiredMixin, ListView):
    """Home page view that displays and handles creation of posts."""
    model = Post
    template_name = 'pages/home.html'
    context_object_name = 'posts'

    def get_queryset(self):
        return get_active_posts()

    def get_context_data(self, **kwargs):
        """Add the post form to the context."""
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm()
        return context

    def post(self, request, *args, **kwargs):
        """Handle post creation."""
        form = PostForm(request.POST)
        if form.is_valid():
            post = Post(
                user_profile=request.user.userprofile,
                content=form.cleaned_data['content'],
                experiment=request.user.userprofile.experiment,
            )
            post.save()
            return redirect('home')
        
        # If form is invalid, show form with errors
        return self.get(request, *args, **kwargs)


class ExploreView(LoginRequiredMixin, ListView):
    """Explore page view that displays all posts."""
    model = Post
    template_name = 'pages/explore.html'
    context_object_name = 'posts'

    def get_queryset(self):
        return get_active_posts()

@login_required
def create_comment(request):
    """Handle creation of comments/replies to posts."""
    if request.method == 'POST':
        parent_id = request.POST.get('parent_post_id')
        content = request.POST.get('content')
        
        if not content:
            return JsonResponse({'status': 'error', 'message': 'Content is required'}, status=400)
            
        try:
            parent_post = Post.objects.get(id=parent_id)
            comment = Post.objects.create(
                user_profile=request.user.userprofile,
                content=content,
                parent_post=parent_post,
                experiment=request.user.userprofile.experiment,
                depth=parent_post.depth + 1
            )
            return JsonResponse({
                'status': 'success',
                'id': str(comment.id),
                'message': 'Comment created successfully'
            })
        except Post.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Parent post not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@login_required
def get_post_replies(request, post_id):
    """Get replies for a specific post."""
    try:
        # Use default manager which already filters out deleted posts
        replies = Post.objects.filter(
            parent_post_id=post_id
        ).select_related(
            'user_profile',
            'user_profile__user'
        ).order_by('created_date')

        replies_data = [{
            'id': str(reply.id),  # Convert UUID to string
            'username': reply.user_profile.username,
            'user_name': reply.user_profile.user.get_full_name() if hasattr(reply.user_profile.user, 'get_full_name') else reply.user_profile.username,
            'content': reply.content,
            'created_date': reply.created_date.isoformat(),
            'user_name': reply.user_profile.user.name,
            'profile_picture': reply.user_profile.profile_picture.url if reply.user_profile.profile_picture else None
        } for reply in replies]
        
        return JsonResponse({'status': 'success', 'replies': replies_data})
    except Post.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
