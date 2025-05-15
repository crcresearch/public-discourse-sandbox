from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView, View, DetailView
from .forms import PostForm, ExperimentForm, EnrollDigitalTwinForm, UserProfileForm
from .models import Post, UserProfile, Experiment, SocialNetwork, DigitalTwin, ExperimentInvitation
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
User = get_user_model()
import json

def get_active_posts(request, experiment=None, hashtag=None):
    """
    Helper function to get active posts. Used in HomeView and ExploreView.
    Get non-deleted top-level posts with related user data.
    
    Args:
        request: The current request object
        experiment: Optional experiment to filter by
        hashtag: Optional hashtag to filter by. If provided, returns posts that either:
            - Have the hashtag directly, OR
            - Have replies containing the hashtag
    """
    posts = Post.objects.filter(
        parent_post__isnull=True,  # Only show top-level posts, not replies
        is_deleted=False  # Only show non-deleted posts
    )
    
    # Filter by experiment if provided
    if experiment:
        posts = posts.filter(experiment=experiment)
    
    # Filter by hashtag if provided - look for posts that either have the hashtag directly
    # or have replies containing the hashtag
    if hashtag:
        posts = posts.filter(
            # Posts that have the hashtag directly OR have replies with the hashtag
            models.Q(hashtag__tag=hashtag.lower()) |  # Direct hashtag match
            models.Q(  # Replies containing the hashtag
                post__hashtag__tag=hashtag.lower(),
                post__is_deleted=False  # Only count non-deleted replies
            )
        ).distinct()  # Use distinct to avoid duplicate posts
    
    # Select related data for efficiency
    posts = posts.select_related(
        'user_profile',
        'user_profile__user'
    ).prefetch_related(
        'vote_set'  # Prefetch votes to avoid N+1 queries
    ).order_by('-created_date')

    # Add comment count and vote status using the get_comment_count method
    for post in posts:
        post.comment_count = post.get_comment_count()
        # Add whether the current user has voted
        post.has_user_voted = post.vote_set.filter(
            user_profile__user=request.user
        ).exists()
    
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


class HomeView(LoginRequiredMixin, ExperimentContextMixin, ProfileRequiredMixin, ListView):
    """Home page view that displays and handles creation of posts."""
    model = Post
    template_name = 'pages/home.html'
    context_object_name = 'posts'

    def get_queryset(self):
        return get_active_posts(request=self.request, experiment=self.experiment)

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
        return get_active_posts(request=self.request, experiment=self.experiment, hashtag=hashtag)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the current hashtag filter to the context
        context['current_hashtag'] = self.request.GET.get('hashtag')
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
        context['reported_posts'] = Post.objects.filter(
            experiment=self.experiment,
            is_deleted=False
        ).order_by('-created_date')[:10]
        
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
        form = EnrollDigitalTwinForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({'error': form.errors.as_json()}, status=400)
        try:
            with transaction.atomic():
                # Create User (custom user model: only email, name, password)
                user = User.objects.create_user(
                    email=form.cleaned_data['email'],
                    password=User.objects.make_random_password(),
                    name=form.cleaned_data['name']
                )
                # Get experiment
                experiment = Experiment.objects.get(identifier=experiment_identifier)
                # Create UserProfile
                user_profile = UserProfile.objects.create(
                    user=user,
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

            # If user is authenticated
            if request.user.is_authenticated:
                # Check if user already has a profile for this experiment
                if UserProfile.objects.filter(user=request.user, experiment=experiment).exists():
                    return render(request, 'pages/accept_invitation.html', {
                        'experiment': experiment,
                        'already_accepted': True,
                        'home_url': reverse('home', kwargs={'experiment_identifier': experiment_identifier})
                    })
                return render(request, 'pages/accept_invitation.html', {
                    'experiment': experiment,
                    'existing_user': True,
                    'create_profile_url': reverse('create_profile', kwargs={'experiment_identifier': experiment_identifier})
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
    template_name = 'pages/user_profile.html'
    context_object_name = 'profile'


class SettingsView(LoginRequiredMixin, TemplateView):
    """
    Settings page view that displays user settings.
    This view is accessible to all authenticated users and is experiment-independent.
    """
    template_name = 'pages/settings.html'
