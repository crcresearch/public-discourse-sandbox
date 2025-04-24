from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.urls import reverse_lazy
from .forms import PostForm
from .models import Post
from django.db import models
from django.http import JsonResponse

def get_active_posts():
    """Get non-deleted top-level posts with related user data."""
    posts = Post.objects.filter(
        parent_post__isnull=True  # Only show top-level posts, not replies
    ).select_related(
        'user_profile',
        'user_profile__user'
    ).order_by('-created_date')

    # Add comment count using the get_comment_count method
    for post in posts:
        post.comment_count = post.get_comment_count()
    
    return posts

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
                depth=0,
                parent_post=None
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
