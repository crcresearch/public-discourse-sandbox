from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView, View
from .forms import PostForm
from .models import Post, UserProfile, Experiment
from .mixins import ExperimentContextMixin
from django.core.exceptions import PermissionDenied
from .decorators import check_banned
from django.utils.decorators import method_decorator

def get_active_posts(experiment=None):
    """Get non-deleted top-level posts with related user data."""
    posts = Post.objects.filter(
        parent_post__isnull=True,  # Only show top-level posts, not replies
        is_deleted=False  # Only show non-deleted posts
    )
    
    # Filter by experiment if provided
    if experiment:
        posts = posts.filter(experiment=experiment)
    
    # Select related data for efficiency
    posts = posts.select_related(
        'user_profile',
        'user_profile__user'
    ).order_by('-created_date')

    # Add comment count using the get_comment_count method
    for post in posts:
        post.comment_count = post.get_comment_count()
    
    return posts


class LandingView(View):
    """
    Landing page view that redirects authenticated users to their home page
    with their last_accessed experiment.
    """
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # If user has a last_accessed experiment, redirect to home with that experiment
            if hasattr(request.user, 'last_accessed') and request.user.last_accessed:
                return redirect('home_with_experiment', experiment_identifier=request.user.last_accessed.identifier)
            # Otherwise, redirect to home which will use ExperimentContextMixin to find an experiment
            return redirect('home')
        # For unauthenticated users, show the landing page
        return render(request, 'pages/landing.html')


class HomeView(LoginRequiredMixin, ExperimentContextMixin, ListView):
    """Home page view that displays and handles creation of posts."""
    model = Post
    template_name = 'pages/home.html'
    context_object_name = 'posts'

    def get_queryset(self):
        return get_active_posts(experiment=self.experiment)

    def get_context_data(self, **kwargs):
        """Add the post form to the context."""
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm()
        return context
        
    @method_decorator(check_banned)
    def post(self, request, *args, **kwargs):
        """Handle post creation."""
        # Get the user's profile for this experiment
        user_profile = request.user.userprofile_set.filter(experiment=self.experiment).first()
        if not user_profile:
            raise PermissionDenied("You do not have a profile in this experiment")
            
        form = PostForm(request.POST)
        if form.is_valid():
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
        return get_active_posts(experiment=self.experiment)


class AboutView(LoginRequiredMixin, ExperimentContextMixin, TemplateView):
    """About page view that displays information about the application."""
    template_name = 'pages/about.html'


class ModeratorDashboardView(LoginRequiredMixin, ExperimentContextMixin, TemplateView):
    """
    Example view that demonstrates all three moderator permission approaches working together.
    """
    template_name = 'pages/moderator_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # 1. Using the mixin's check_moderator_permission method
        self.check_moderator_permission()
        
        # 2. Using the model method directly
        user_profile = request.user.userprofile_set.filter(experiment=self.experiment).first()
        if not user_profile.is_experiment_moderator():
            raise PermissionDenied("You do not have moderator permissions for this experiment.")
            
        return super().get(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 3. The context processor automatically adds is_moderator to the context
        # 4. The mixin also adds is_moderator to the context
        # Both will be True at this point because we've already checked permissions
        
        # Add some moderator-specific data
        context['banned_users'] = UserProfile.objects.filter(
            experiment=self.experiment,
            is_banned=True
        )
        context['reported_posts'] = Post.objects.filter(
            experiment=self.experiment,
            is_deleted=False
        ).order_by('-created_date')[:10]
        
        return context
