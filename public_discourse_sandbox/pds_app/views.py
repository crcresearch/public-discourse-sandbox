from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .forms import PostForm
from .models import Post
from .mixins import ExperimentContextMixin
from django.core.exceptions import PermissionDenied

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


class HomeView(LoginRequiredMixin, ExperimentContextMixin, ListView):
    """Home page view that displays and handles creation of posts."""
    model = Post
    template_name = 'pages/home.html'
    context_object_name = 'posts'

    def get_queryset(self):
        if self.experiment:
            return get_active_posts().filter(experiment=self.experiment)
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
            # Get the user's profile for this experiment
            user_profile = request.user.userprofile_set.filter(experiment=self.experiment).first()
            if not user_profile:
                raise PermissionDenied("You do not have a profile in this experiment")
                
            post = Post(
                user_profile=user_profile,
                content=form.cleaned_data['content'],
                experiment=self.experiment,
                depth=0,
                parent_post=None
            )
            post.save()
            # Redirect to the appropriate URL based on whether we have an experiment identifier
            if 'experiment_identifier' in kwargs:
                return redirect('home_with_experiment', experiment_identifier=self.experiment.identifier)
            return redirect('home')
        
        # If form is invalid, show form with errors
        return self.get(request, *args, **kwargs)


class ExploreView(LoginRequiredMixin, ExperimentContextMixin, ListView):
    """Explore page view that displays all posts."""
    model = Post
    template_name = 'pages/explore.html'
    context_object_name = 'posts'

    def get_queryset(self):
        if self.experiment:
            return get_active_posts().filter(experiment=self.experiment)
        return get_active_posts()
