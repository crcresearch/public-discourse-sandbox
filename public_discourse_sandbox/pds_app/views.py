from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView, View, DetailView
from .forms import PostForm, ExperimentForm, EnrollDigitalTwinForm, UserProfileForm
from .models import Post, UserProfile, Experiment, SocialNetwork, DigitalTwin, ExperimentInvitation, Notification
from .mixins import ExperimentContextMixin, ProfileRequiredMixin
from django.core.exceptions import PermissionDenied
from .decorators import check_banned
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db import models, transaction
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url
from django.utils.translation import gettext_lazy as _
User = get_user_model()
import json


def get_active_posts(request, experiment=None, hashtag=None, profile_ids=None, previous_post_id=None, page_size=10):
    """
    Helper function to get active posts. Used in HomeView and ExploreView.
    Get non-deleted top-level posts with related user data.
    
    Args:
        request: The current request object
        experiment: Optional experiment to filter by
        hashtag: Optional hashtag to filter by. If provided, returns posts that either:
            - Have the hashtag directly, OR
            - Have replies containing the hashtag
        profile_ids: Optional list of profile IDs to filter by
        previous_post_id: Optional ID of the last post from previous page to paginate from
        page_size: Number of posts to return per page (default: 20)
    """


    # Filter by hashtag if provided - look for posts that either have the hashtag directly
    # or have replies containing the hashtag
    if hashtag:
        posts = Post.objects.filter(
            models.Q(hashtag__tag=hashtag.lower(), parent_post__isnull=True) |  # Top-level posts with hashtag
            models.Q(  # Replies with hashtag where parent exists and isn't deleted
                hashtag__tag=hashtag.lower(),
                parent_post__isnull=False,
                parent_post__is_deleted=False
            )
        ).distinct()  # Use distinct to avoid duplicate posts
    else:
        posts = Post.objects.filter(
            parent_post__isnull=True,  # Only show top-level posts, not replies
            is_deleted=False  # Only show non-deleted posts
        )
    
    # Filter by experiment if provided
    if experiment:
        posts = posts.filter(experiment=experiment)
    
    # Filter by profile IDs if provided 
    if profile_ids:
        posts = posts.filter(user_profile__in=profile_ids)
    

        # Determine next page of posts based on previous_post_id's created_date
    if previous_post_id:
        try:
            previous_post = Post.objects.get(id=previous_post_id)
            posts = posts.filter(created_date__lt=previous_post.created_date)
        except Post.DoesNotExist:
            # If previous_post_id is not found, start at current time. Case is when user first loads the page.
            pass
    
    # Select related data for efficiency
    posts = posts.select_related(
        'user_profile',
        'user_profile__user'
    ).prefetch_related(
        'vote_set'  # Prefetch votes to avoid N+1 queries
    ).order_by('-created_date')


    # Limit results to page_size
    posts = posts[:int(page_size)]

    # Get current user's profile for follow state checks
    current_user_profile = None
    if request.user.is_authenticated and experiment:
        current_user_profile = request.user.userprofile_set.filter(experiment=experiment).first()

    # Add comment count, vote status, and follow state using the get_comment_count method
    for post in posts:
        post.comment_count = post.get_comment_count()
        # Add whether the current user has voted
        post.has_user_voted = post.vote_set.filter(
            user_profile__user=request.user
        ).exists()
        
        # Add follow state for each post
        if current_user_profile and post.user_profile.user != request.user:
            post.is_following = SocialNetwork.objects.filter(
                source_node=current_user_profile,
                target_node=post.user_profile
            ).exists()
        else:
            post.is_following = False
    
    return posts


def get_home_feed_posts(request, experiment=None, previous_post_id=None, page_size=10):
    """
    Helper function to get posts for the home feed.
    Only returns posts from the current user and users they follow.
    
    Args:
        request: The current request object
        experiment: Optional experiment to filter by
    """
    # Get the user's profile for this experiment
    user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
    
    if not user_profile:
        return Post.objects.none()  # Return empty queryset if no profile
    
    # Get IDs of users the current user follows
    following_ids = SocialNetwork.objects.filter(
        source_node=user_profile
    ).values_list('target_node', flat=True)
    
    # Add the user's own profile to the list
    profile_ids = list(following_ids) + [user_profile.id]
    
    # Get all active posts with filtering by profile IDs from the beginning
    return get_active_posts(request, experiment, profile_ids=profile_ids, previous_post_id=previous_post_id, page_size=page_size)


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
        # Fetch the default experiment to display IRB additions
        try:
            default_experiment = Experiment.objects.get(identifier="00000")  # TODO: Find a better way to handle this
            return render(request, 'pages/landing.html', {'experiment': default_experiment})
        except Experiment.DoesNotExist:
            # If default experiment doesn't exist, just render without it
            return render(request, 'pages/landing.html')


class HomeView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, ListView):
    """Home page view that displays and handles creation of posts."""
    model = Post
    template_name = 'pages/home.html'
    context_object_name = 'posts'

    def get_queryset(self):
        previous_post_id = self.request.GET.get('previous_post_id', None)
        page_size = self.request.GET.get('page_size', None)

        # Only pass pagination params if they were provided
        kwargs = {
            'request': self.request,
            'experiment': self.experiment
        }
        if previous_post_id is not None:
            kwargs['previous_post_id'] = previous_post_id
        if page_size is not None:
            kwargs['page_size'] = page_size

        return get_home_feed_posts(**kwargs)

    def get_context_data(self, **kwargs):
        """Add the post form to the context."""
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm()
        
        # Add flag for empty home feed to show guidance message
        if not context['posts'] and not self.request.headers.get('HX-Request'):
            user_profile = self.request.user.userprofile_set.filter(experiment=self.experiment).first()
            if user_profile:
                # Check if user follows anyone
                follows_anyone = SocialNetwork.objects.filter(source_node=user_profile).exists()
                # Check if user has posted anything
                has_posted = Post.objects.filter(user_profile=user_profile, is_deleted=False).exists()
                
                context['empty_home_feed'] = True
                context['follows_anyone'] = follows_anyone
                context['has_posted'] = has_posted
        
        return context
    
    @method_decorator(check_banned)
    def get(self, request, *args, **kwargs):
        """Override get to handle HTMX requests."""
        if request.headers.get('HX-Request'):
            self.template_name = 'partials/_post_list.html'
        return super().get(request, *args, **kwargs)
        
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


class ExploreView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, ListView):
    """
    Explore page view that displays all posts.
    Supports filtering by hashtag using the 'hashtag' query parameter.
    """
    model = Post
    template_name = 'pages/explore.html'
    context_object_name = 'posts'

    def get_queryset(self):
        # Get hashtag from query parameters
        hashtag = self.request.GET.get('hashtag')
        previous_post_id = self.request.GET.get('previous_post_id', None)
        page_size = self.request.GET.get('page_size', None)

        # Only pass pagination params if they were provided
        kwargs = {
            'request': self.request,
            'experiment': self.experiment,
            'hashtag': hashtag
        }
        if previous_post_id is not None:
            kwargs['previous_post_id'] = previous_post_id
        if page_size is not None:
            kwargs['page_size'] = page_size

        return get_active_posts(**kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the current hashtag filter to the context
        context['current_hashtag'] = self.request.GET.get('hashtag')
        return context

    @method_decorator(check_banned)
    def get(self, request, *args, **kwargs):
        """Override get to handle HTMX requests."""
        if request.headers.get('HX-Request'):
            self.template_name = 'partials/_post_list.html'
        return super().get(request, *args, **kwargs)
    
class NotificationsView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, ListView):
    template_name = 'pages/notifications.html'
    context_object_name = 'notifications'
        
    def get_queryset(self):
        """Get notifications for the current user in the current experiment."""
        # Get filter parameter
        filter_type = self.request.GET.get('filter')
        previous_notification_id = self.request.GET.get('previous_notification_id')
        page_size = self.request.GET.get('page_size', 20)  # Default to 20 notifications per page
        
        # Start with all notifications for this user profile
        notifications = Notification.objects.filter(
            user_profile=self.user_profile
        )
        
        # Apply filtering if specified
        if filter_type and filter_type != 'all':
            notifications = notifications.filter(event=filter_type)
        
        # Apply pagination if specified
        if previous_notification_id:
            try:
                previous_notification = Notification.objects.get(id=previous_notification_id)
                notifications = notifications.filter(created_date__lt=previous_notification.created_date)
            except Notification.DoesNotExist:
                pass
        
        # Order by most recent first and limit to page size
        return notifications.order_by('-created_date')[:int(page_size)]
    
    def get(self, request, *args, **kwargs):
        """
        Override the get method to mark all notifications as read when the user
        accesses the notifications page, but preserve which ones were unread.
        Also handle HTMX requests for infinite scroll.
        """
        # First, get all unread notifications
        unread_notifications = [str(id) for id in Notification.objects.filter(
            user_profile=self.user_profile,
            is_read=False
        ).values_list('id', flat=True)]
        
        # Mark all unread notifications as read
        Notification.objects.filter(
            user_profile=self.user_profile,
            is_read=False
        ).update(is_read=True)
        
        # Store the IDs of previously unread notifications in the request
        # so they can be accessed in get_context_data
        request.unread_notification_ids = unread_notifications
        
        # For HTMX requests, return only the notification list partial
        if request.headers.get('HX-Request'):
            self.template_name = 'partials/_notification_list.html'
        
        # Call the parent get method to render the page as usual
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add information about which notifications were previously unread."""
        context = super().get_context_data(**kwargs)
        
        # Get the list of previously unread notification IDs from the request
        unread_ids = getattr(self.request, 'unread_notification_ids', [])
        
        # Mark notifications that were previously unread
        for notification in context['notifications']:
            notification.was_unread = str(notification.id) in unread_ids
        
        # Add the current filter to the context
        context['current_filter'] = self.request.GET.get('filter', 'all')
        
        return context

class AboutView(LoginRequiredMixin, ExperimentContextMixin, TemplateView):
    """About page view that displays information about the application."""
    template_name = 'pages/about.html'


class ModeratorDashboardView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, TemplateView):
    """
    Example view that demonstrates all three moderator permission approaches working together.
    """
    template_name = 'pages/moderator_dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # 1. Using the mixin's check_moderator_permission method
        if not self.is_moderator(request.user, self.experiment):
            # Redirect to home page if not a moderator
            return redirect('home_with_experiment', experiment_identifier=self.experiment.identifier)
            
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
        
        # Recent posts for moderation (first tab)
        context['reported_posts'] = Post.objects.filter(
            experiment=self.experiment,
            is_deleted=False
        ).order_by('-created_date')[:10]
        
        # Flagged posts for profanity (second tab)
        flagged_posts = Post.objects.filter(
            experiment=self.experiment,
            is_deleted=False,
            is_flagged=True
        ).order_by('-created_date')
        
        context['flagged_posts'] = flagged_posts
        context['flagged_posts_count'] = flagged_posts.count()
        
        return context


class FollowView(LoginRequiredMixin, View):
    """
    View to handle following/unfollowing users.
    """
    def post(self, request, *args, **kwargs):
        try:
            # Get the target user profile from URL parameter
            target_profile = UserProfile.objects.get(id=kwargs['user_profile_id'])
            
            # Get the current user's profile for this experiment
            user_profile = request.user.userprofile_set.filter(experiment=target_profile.experiment).first()
            if not user_profile:
                raise PermissionDenied("You do not have a profile in this experiment")
            
            # Check if already following
            existing_follow = SocialNetwork.objects.filter(
                source_node=user_profile,
                target_node=target_profile
            ).first()
            
            if existing_follow:
                # Unfollow
                existing_follow.delete()
                is_following = False
            else:
                # Follow
                SocialNetwork.objects.create(
                    source_node=user_profile,
                    target_node=target_profile
                )
                is_following = True
                # Create a notification for the target user
                Notification.objects.create(
                    user_profile=target_profile,
                    event='follow',
                    content=f'@{user_profile.username} followed you'
                )
            
            return JsonResponse({
                'status': 'success',
                'is_following': is_following,
                'follower_count': target_profile.num_followers
            })
            
        except UserProfile.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'User profile not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


class ResearcherToolsView(LoginRequiredMixin, TemplateView):
    """
    View for researcher tools page that displays experiments where the user is either
    the creator or a collaborator.
    """
    template_name = 'pages/researcher_tools.html'
    
    def get(self, request, *args, **kwargs):
        # Check if user is in researcher group
        if not request.user.groups.filter(name='researcher').exists():
            raise PermissionDenied("You must be a researcher to access this page")
            
        return super().get(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get experiments where user is creator or collaborator
        # Note: We don't need to filter is_deleted=False here because the default manager already does that
        user_experiments = Experiment.objects.filter(
            models.Q(creator=self.request.user) |  # User is creator
            models.Q(userprofile__user=self.request.user, userprofile__is_collaborator=True)  # User is collaborator
        ).distinct().order_by('-created_date')  # Order by most recent first
        
        # Annotate each experiment with statistics
        user_experiments = user_experiments.annotate(
            # Count active users (not bots, not banned, not soft-deleted)
            total_users=models.Count(
                'userprofile',
                filter=models.Q(
                    userprofile__is_digital_twin=False,
                    userprofile__is_banned=False,
                    userprofile__is_deleted=False
                ),
                distinct=True
            ),
            # Count banned users
            total_banned_users=models.Count(
                'userprofile',
                filter=models.Q(
                    userprofile__is_banned=True,
                    userprofile__is_deleted=False
                ),
                distinct=True
            ),
            total_posts=models.Count(
                'post',
                filter=models.Q(post__is_deleted=False),
                distinct=True
            ),
            total_digital_twins=models.Count(
                'userprofile',
                filter=models.Q(
                    userprofile__is_digital_twin=True,
                    userprofile__is_deleted=False
                ),
                distinct=True
            )
        )
        
        context['experiments'] = user_experiments
        return context


class CreateExperimentView(LoginRequiredMixin, TemplateView):
    """
    View for creating a new experiment.
    """
    template_name = 'pages/create_experiment.html'
    
    def get(self, request, *args, **kwargs):
        # Check if user is in researcher group
        if not request.user.groups.filter(name='researcher').exists():
            raise PermissionDenied("You must be a researcher to access this page")
            
        return super().get(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ExperimentForm()
        return context
        
    def post(self, request, *args, **kwargs):
        """Handle experiment creation."""
        form = ExperimentForm(request.POST)
        if form.is_valid():
            experiment = form.save(commit=False)
            experiment.creator = request.user
            experiment.save()
            messages.success(request, 'Experiment created successfully!')
            return redirect('researcher_tools')
            
        # If form is invalid, show form with errors
        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


class ExperimentDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying experiment details.
    """
    model = Experiment
    template_name = 'pages/experiment_detail.html'
    context_object_name = 'experiment'
    slug_field = 'identifier'
    slug_url_kwarg = 'experiment_identifier'
    
    def get(self, request, *args, **kwargs):
        # Check if user is in researcher group
        if not request.user.groups.filter(name='researcher').exists():
            raise PermissionDenied("You must be a researcher to access this page")
            
        # Get the experiment
        self.object = self.get_object()
        
        # Check if experiment is deleted
        if self.object.is_deleted:
            messages.error(request, 'This experiment has been deleted.')
            return redirect('researcher_tools')
        
        # Check if user has access to this experiment
        if not (self.object.creator == request.user or 
                self.object.userprofile_set.filter(user=request.user, is_collaborator=True).exists()):
            raise PermissionDenied("You do not have access to this experiment")
            
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
        
    def get_queryset(self):
        """
        Override get_queryset to use all_objects instead of objects.
        This allows us to access deleted experiments for the detail view.
        """
        return Experiment.all_objects.all()
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        experiment = self.object
        
        # Add experiment statistics with proper filtering
        context['total_users'] = experiment.userprofile_set.filter(
            is_digital_twin=False,
            is_banned=False,
            is_deleted=False
        ).count()
        
        context['total_banned_users'] = experiment.userprofile_set.filter(
            is_banned=True,
            is_deleted=False
        ).count()
        
        context['total_posts'] = experiment.post_set.filter(is_deleted=False).count()
        context['total_digital_twins'] = experiment.userprofile_set.filter(
            is_digital_twin=True,
            is_deleted=False
        ).count()
        
        # Add form for editing if user is creator
        if experiment.creator == self.request.user:
            context['form'] = ExperimentForm(instance=experiment)
            
        # Hide main nav on experiment detail page
        context['hide_main_nav'] = True
        context['invitations'] = ExperimentInvitation.objects.filter(experiment=experiment, is_deleted=False)
        return context
        
    def post(self, request, *args, **kwargs):
        """Handle experiment updates."""
        experiment = self.get_object()
        
        # Only creator can edit
        if experiment.creator != request.user:
            raise PermissionDenied("Only the experiment creator can edit this experiment")
            
        form = ExperimentForm(request.POST, instance=experiment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Experiment updated successfully!')
            return redirect('experiment_detail', experiment_identifier=experiment.identifier)
            
        # If form is invalid, show form with errors
        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


class InviteUserView(LoginRequiredMixin, View):
    """
    View for inviting users to an experiment.
    """
    def post(self, request, experiment_identifier):
        try:
            # Get the experiment
            experiment = Experiment.objects.get(identifier=experiment_identifier)
            
            # Check if user has permission to invite (must be creator)
            if experiment.creator != request.user:
                return JsonResponse({'error': 'You do not have permission to invite users to this experiment'}, status=403)
            
            # Get email from request
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)
            
            # Check if a user with this email exists and is already a member of the experiment
            user = User.objects.filter(email=email).first()
            if user:
                if UserProfile.objects.filter(user=user, experiment=experiment, is_deleted=False).exists():
                    return JsonResponse({'message': 'User is already a member of this experiment.'}, status=400)
            
            # Create the invitation if not already invited
            invitation, created = ExperimentInvitation.objects.get_or_create(
                experiment=experiment,
                email=email,
                created_by=request.user
            )
            if created:
                # Send invitation email
                # Get a name or email for the user who is being invited
                contact_name = request.user.name or request.user.email
                context = {
                    'user': request.user,
                    'study': {
                        'invitee_name': email,
                        'title': experiment.name,
                        'description': experiment.description,
                        'contact_name': contact_name,
                        'contact_email': request.user.email,
                        'duration': 'Ongoing',
                        'compensation': 'None',
                        'irb_information': 'This study has been approved by the University of Notre Dame IRB.'
                    },
                    'experiment': experiment,
                    'accept_url': request.build_absolute_uri(reverse('accept_invitation', args=[experiment.identifier, email])),
                    'landing_url': request.build_absolute_uri(reverse('landing'))
                }
                
                # Send email
                send_mail(
                    subject='Research Study Invitation - Public Discourse Sandbox',
                    message='',  # Plain text version will be generated from HTML
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=render_to_string('email/research_invitation.html', context)
                )
                
                return JsonResponse({'message': 'Invitation sent successfully'})
            else:
                return JsonResponse({'message': 'User already invited'}, status=400)
            
        except Experiment.DoesNotExist:
            return JsonResponse({'error': 'Experiment not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class EnrollDigitalTwinView(LoginRequiredMixin, View):
    def post(self, request, experiment_identifier):
        try:
            # Get experiment first so we can pass it to the form
            experiment = Experiment.objects.get(identifier=experiment_identifier)
            
            # Pass experiment to the form
            form = EnrollDigitalTwinForm(request.POST, request.FILES, experiment=experiment)
            if not form.is_valid():
                return JsonResponse({'error': form.errors.as_json()}, status=400)
                
            with transaction.atomic():
                # Create UserProfile
                user_profile = UserProfile.objects.create(
                    display_name=form.cleaned_data['display_name'],
                    username=form.cleaned_data['username'],
                    experiment=experiment,
                    bio=form.cleaned_data.get('bio', ''),
                    is_digital_twin=True
                )
                # Handle images
                if form.cleaned_data.get('banner_picture'):
                    user_profile.banner_picture = form.cleaned_data['banner_picture']
                if form.cleaned_data.get('profile_picture'):
                    user_profile.profile_picture = form.cleaned_data['profile_picture']
                user_profile.save()
                # Create DigitalTwin
                DigitalTwin.objects.create(
                    user_profile=user_profile,
                    persona=form.cleaned_data.get('persona', ''),
                    api_token=form.cleaned_data.get('api_token', ''),
                    llm_url=form.cleaned_data.get('llm_url', ''),
                    llm_model=form.cleaned_data.get('llm_model', '')
                )
            return JsonResponse({'message': 'Digital Twin enrolled successfully!'})
        except Experiment.DoesNotExist:
            return JsonResponse({'error': 'Experiment not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class CreateProfileView(LoginRequiredMixin, View):
    """
    View for creating a user profile for a specific experiment.
    Requires user to be logged in and experiment identifier to be valid.
    """
    template_name = 'pages/create_profile.html'
    
    def get(self, request, experiment_identifier):
        # Check if experiment exists
        try:
            experiment = Experiment.objects.get(identifier=experiment_identifier)
        except Experiment.DoesNotExist:
            return render(request, self.template_name, {
                'error': 'Invalid experiment identifier'
            })
            
        # Check if user already has a profile for this experiment
        existing_profile = UserProfile.objects.filter(
            user=request.user,
            experiment=experiment,
            is_deleted=False
        ).first()
        
        if existing_profile:
            return render(request, self.template_name, {
                'experiment': experiment,
                'existing_profile': existing_profile,
                'home_url': reverse('home_with_experiment', kwargs={'experiment_identifier': experiment.identifier})
            })
            
        # If no existing profile, show the create profile form
        return render(request, self.template_name, {
            'experiment': experiment,
            'form': UserProfileForm(experiment=experiment)
        })
        
    def post(self, request, experiment_identifier):
        try:
            experiment = Experiment.objects.get(identifier=experiment_identifier)
        except Experiment.DoesNotExist:
            return render(request, self.template_name, {
                'error': 'Invalid experiment identifier'
            })
            
        # Check if user already has a profile
        if UserProfile.objects.filter(user=request.user, experiment=experiment, is_deleted=False).exists():
            return render(request, self.template_name, {
                'experiment': experiment,
                'error': 'You already have a profile for this experiment'
            })
            
        form = UserProfileForm(request.POST, request.FILES, experiment=experiment)
        if form.is_valid():
            # Create the profile
            profile = form.save(commit=False)
            profile.user = request.user
            profile.experiment = experiment
            profile.save()
            
            # Redirect to the experiment's home page
            return redirect('home_with_experiment', experiment_identifier=experiment.identifier)
            
        # If form is invalid, show form with errors
        return render(request, self.template_name, {
            'experiment': experiment,
            'form': form
        })


class AcceptInvitationView(View):
    """
    View for handling invitation acceptance.
    Updated: If the invitation email matches an existing User and the user is not authenticated,
    redirect to login with a 'next' parameter to return to this page after login.
    """
    def get(self, request, *args, **kwargs):
        experiment_identifier = kwargs.get('experiment_identifier')
        email = kwargs.get('email')
        User = get_user_model()
        
        if not email:
            return render(request, 'pages/accept_invitation.html', {
                'error': _('No email address provided.')
            })
        
        try:
            experiment = Experiment.objects.get(identifier=experiment_identifier)
            invitation = ExperimentInvitation.objects.get(
                experiment=experiment,
                email=email,
                is_accepted=False,
                is_deleted=False
            )

            # Check if the invitation email matches an existing user
            user_exists = User.objects.filter(email__iexact=email).exists()

            # If not authenticated and the email matches a user, redirect to login
            if user_exists and not request.user.is_authenticated:
                # Use Django's built-in login view, with 'next' param to return here after login
                # login_url = reverse('login')
                login_url = resolve_url(settings.LOGIN_URL)
                next_url = request.get_full_path()
                return redirect_to_login(next_url, login_url)

            # If user is authenticated and the email matches the current user, check if they already have a profile for this experiment
            if request.user.is_authenticated:
                if str(request.user.email) == str(email):
                    # Check if user already has a profile for this experiment
                    try:
                        user_profile = UserProfile.objects.get(user=request.user, experiment=experiment)
                        return render(request, 'pages/accept_invitation.html', {
                            'experiment': experiment,
                            'already_accepted': True,
                            'home_url': reverse('home_with_experiment', kwargs={'experiment_identifier': experiment_identifier}),
                            'current_user_profile': user_profile
                        })
                    except UserProfile.DoesNotExist:
                        return render(request, 'pages/accept_invitation.html', {
                            'experiment': experiment,
                            'existing_user': True,
                            'create_profile_url': reverse('create_profile', kwargs={'experiment_identifier': experiment_identifier}),
                            'current_user_profile': None
                        })
                else:
                    # User Profile is needed for left nav context
                    try:
                        user_profile = UserProfile.objects.get(user=request.user, experiment=experiment)
                    except UserProfile.DoesNotExist:
                        user_profile = None
                    return render(request, 'pages/accept_invitation.html', {
                        'experiment': experiment,
                        'error': _('You are logged in as ' + str(request.user) + ' but the invitation link is for ' + str(email) + '. To check invitation status, please either log in as ' + str(email) + ' or log out and try again.'),
                        'current_user_profile': user_profile
                    })
            else:
                # If the email does not match a user, proceed to signup
                signup_url = reverse('users:signup_with_profile') + f'?experiment={experiment_identifier}&email={email}'
                return render(request, 'pages/accept_invitation.html', {
                    'experiment': experiment,
                    'existing_user': False,
                    'signup_url': signup_url
                })
                
        except Experiment.DoesNotExist:
            return render(request, 'pages/accept_invitation.html', {
                'error': _('Invalid experiment.')
            })
        except ExperimentInvitation.DoesNotExist:
            return render(request, 'pages/accept_invitation.html', {
                'error': _('Invalid or expired invitation link.')
            })

class UserProfileDetailView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, DetailView):
    """
    View for displaying a user's profile.
    """
    model = UserProfile
    template_name = 'users/user_profile_detail.html'
    context_object_name = 'viewed_profile'
    slug_url_kwarg = 'user_profile_id'


    def get_context_data(self, **kwargs):
        """
        Add experiment and profile context to template context.
        """
        context = super().get_context_data(**kwargs)
        # The ExperimentContextMixin already adds:
        # - experiment
        # - current_user_profile (the current user's profile in this experiment)
        # - is_moderator (current user's moderator status)
        
        # Add the viewed profile's role information
        context['viewed_profile'] = self.object
        context['is_creator'] = self.object.user == self.experiment.creator

        # Add follower and following counts
        context['follower_count'] = SocialNetwork.objects.filter(target_node=self.object).count()
        context['following_count'] = SocialNetwork.objects.filter(source_node=self.object).count()

        # Get pagination parameters
        previous_post_id = self.request.GET.get('previous_post_id', None)
        page_size = self.request.GET.get('page_size', 10)  # Default to 10 posts per page
        replies_only = self.request.GET.get('replies_only', False)  # New param to optionally show replies only

        # Get all posts by this user (not deleted, ordered by newest first)
        all_posts = Post.all_objects.filter(user_profile=self.object, is_deleted=False).select_related(
            'user_profile',
            'user_profile__user',
            'parent_post',
            'parent_post__user_profile',
            'parent_post__user_profile__user'
        ).prefetch_related('vote_set')

        # Separate original posts and replies
        original_posts = all_posts.filter(parent_post__isnull=True)
        replies = all_posts.filter(parent_post__isnull=False, parent_post__is_deleted=False)

        # If previous_post_id provided, paginate from that post
        if previous_post_id:
            try:
                previous_post = Post.objects.get(id=previous_post_id)
                original_posts = original_posts.filter(created_date__lt=previous_post.created_date)
                replies = replies.filter(created_date__lt=previous_post.created_date)
            except Post.DoesNotExist:
                pass

        # Order by newest first and limit to page size
        context['user_original_posts'] = original_posts.order_by('-created_date')[:int(page_size)]
        context['user_replies'] = replies.order_by('-created_date')[:int(page_size)]
        
        # Add counts for the tabs
        context['original_posts_count'] = original_posts.count()
        context['replies_count'] = replies.count()

        # Keep the original user_posts for backward compatibility (all posts)
        # If replies_only is True, show only replies, otherwise show only original posts
        if replies_only:
            context['user_posts'] = replies.order_by('-created_date')[:int(page_size)]
        else:
            context['user_posts'] = original_posts.order_by('-created_date')[:int(page_size)]
        
        # Annotate each post with comment_count and has_user_voted for template compatibility
        current_user = self.request.user
        current_user_profile = context.get('current_user_profile')
        for post_list in [context['user_original_posts'], context['user_replies'], context['user_posts']]:
            for post in post_list:
                post.comment_count = post.get_comment_count()
                post.has_user_voted = post.vote_set.filter(user_profile__user=current_user).exists()
                
                # Add follow state for each post
                if current_user_profile and post.user_profile.user != current_user:
                    post.is_following = SocialNetwork.objects.filter(
                        source_node=current_user_profile,
                        target_node=post.user_profile
                    ).exists()
                else:
                    post.is_following = False

        # If HTMX request, map user_posts to posts for template compatibility
        if self.request.headers.get('HX-Request'):
            context['posts'] = context['user_posts']

        # Add whether the current user is following the viewed profile
        if current_user_profile:
            context['is_following_viewed_profile'] = SocialNetwork.objects.filter(source_node=current_user_profile, target_node=self.object).exists()
        else:
            context['is_following_viewed_profile'] = False
        
        # Followers: UserProfiles that follow this profile
        follower_links = SocialNetwork.objects.filter(target_node=self.object)
        context['followers'] = UserProfile.objects.filter(id__in=follower_links.values_list('source_node', flat=True))

        # Following: UserProfiles that this profile follows
        following_links = SocialNetwork.objects.filter(source_node=self.object)
        context['following'] = UserProfile.objects.filter(id__in=following_links.values_list('target_node', flat=True))
        
        return context
    
    @method_decorator(check_banned)
    def get(self, request, *args, **kwargs):
        """Override get to handle HTMX requests."""
        if request.headers.get('HX-Request'):
            self.template_name = 'partials/_post_list.html'
        return super().get(request, *args, **kwargs)


class SettingsView(LoginRequiredMixin, TemplateView):
    """
    Settings page view that displays user settings.
    This view is accessible to all authenticated users and is experiment-independent.
    """
    template_name = 'pages/settings.html'


class CommentDetailView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, DetailView):
    """
    View for displaying comment detail modal content via HTMX.
    Returns the modal content for a specific post and its replies.
    """
    model = Post
    template_name = 'partials/_comment_modal_content.html'
    context_object_name = 'post'
    slug_field = 'id'
    slug_url_kwarg = 'post_id'
    
    def get_queryset(self):
        """Filter posts by experiment and ensure they're not deleted."""
        return Post.objects.filter(
            experiment=self.experiment,
            is_deleted=False
        ).select_related(
            'user_profile',
            'user_profile__user'
        ).prefetch_related('vote_set')
    
    def get_context_data(self, **kwargs):
        """Add replies and other context data for the modal."""
        context = super().get_context_data(**kwargs)
        post = self.object
        
        # Get current user's profile for follow state checks
        current_user_profile = context.get('current_user_profile')
        
        # Add comment count and vote status for the main post
        post.comment_count = post.get_comment_count()
        post.has_user_voted = post.vote_set.filter(
            user_profile__user=self.request.user
        ).exists()
        
        # Add follow state for the main post
        if current_user_profile and post.user_profile.user != self.request.user:
            post.is_following = SocialNetwork.objects.filter(
                source_node=current_user_profile,
                target_node=post.user_profile
            ).exists()
        else:
            post.is_following = False
        
        # Get replies for this post
        replies = Post.objects.filter(
            parent_post=post,
            is_deleted=False
        ).select_related(
            'user_profile',
            'user_profile__user'
        ).prefetch_related('vote_set').order_by('created_date')
        
        # Add comment count, vote status, and follow state for each reply
        for reply in replies:
            reply.comment_count = reply.get_comment_count()
            reply.has_user_voted = reply.vote_set.filter(
                user_profile__user=self.request.user
            ).exists()
            # Add permission flags for template
            reply.is_author = reply.user_profile.user == self.request.user
            reply.is_moderator = self.is_moderator(self.request.user, self.experiment)
            
            # Add follow state for each reply
            if current_user_profile and reply.user_profile.user != self.request.user:
                reply.is_following = SocialNetwork.objects.filter(
                    source_node=current_user_profile,
                    target_node=reply.user_profile
                ).exists()
            else:
                reply.is_following = False
        
        context['replies'] = replies
        
        # Add user profile URL template for JavaScript
        context['user_profile_url_template'] = reverse(
            'user_profile_detail', 
            kwargs={
                'experiment_identifier': self.experiment.identifier,
                'pk': '00000000-0000-0000-0000-000000000000'
            }
        )
        
        return context
    
    @method_decorator(check_banned)
    def get(self, request, *args, **kwargs):
        """Handle GET requests for comment modal content."""
        return super().get(request, *args, **kwargs)
