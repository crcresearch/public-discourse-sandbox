from .models import DigitalTwin
from django.contrib.auth.models import User
from public_discourse_sandbox.pds_app.models import Experiment
from django.db.models import Count
from .models import Hashtag
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

def active_bots(request):
    """
    Context processor that adds active bots to all templates.
    This allows us to display the active bots count in the sidebar
    without having to add it to every view's context.
    """
    if not request.user.is_authenticated:
        return {'active_bots': []}
    
    # Get the current experiment from the URL or session
    experiment_identifier = request.resolver_match.kwargs.get('experiment_identifier')
    if not experiment_identifier:
        return {'active_bots': []}
    
    try:
        experiment = Experiment.objects.get(identifier=experiment_identifier)
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return {'active_bots': []}
        
        return {
            'active_bots': DigitalTwin.objects.filter(
                is_active=True, 
                user_profile__experiment=experiment
            )
        }
    except Experiment.DoesNotExist:
        return {'active_bots': []}

def user_experiments(request):
    """
    Context processor that adds the user's experiments to the template context.
    Returns an empty list if user is not authenticated.
    """
    if not request.user.is_authenticated:
        return {'user_experiments': [], 'current_experiment_identifier': None}
    
    # Get all experiments where the user has a UserProfile
    experiments = Experiment.objects.filter(
        userprofile__user=request.user
    ).distinct().order_by('name')
    
    # Get the current experiment identifier from the URL
    current_experiment_identifier = request.resolver_match.kwargs.get('experiment_identifier')
    
    return {
        'user_experiments': experiments,
        'current_experiment_identifier': current_experiment_identifier
    }

def is_moderator(request):
    """
    Context processor that adds is_moderator flag to all templates.
    Uses the UserProfile's is_experiment_moderator method.
    """
    if not request.user.is_authenticated:
        return {'is_moderator': False}
    
    # Get the current experiment from the URL or session
    experiment_identifier = request.resolver_match.kwargs.get('experiment_identifier')
    if not experiment_identifier:
        return {'is_moderator': False}
    
    try:
        experiment = Experiment.objects.get(identifier=experiment_identifier)
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        
        if not user_profile:
            return {'is_moderator': False}
            
        return {'is_moderator': user_profile.is_experiment_moderator()}
    except Experiment.DoesNotExist:
        return {'is_moderator': False}

def trending_hashtags(request):
    """
    Context processor that adds trending hashtags to the template context.
    Only adds trending hashtags if the user is authenticated and has a current experiment.
    Returns the top 5 trending hashtags for the current experiment.
    
    Caching Mechanism:
    - Results are cached using Django's cache framework
    - Cache key format: 'trending_hashtags_{experiment_identifier}'
    - Cache is invalidated when a new hashtag is saved via the post_save signal
    - Cache persists until a new hashtag is added to the experiment
    
    Query Logic:
    - Filters hashtags by the current experiment
    - Groups by tag to get unique hashtags
    - Counts distinct occurrences of each hashtag
    - Orders by count in descending order
    - Returns top 5 hashtags with their counts
    """
    if not request.user.is_authenticated:
        return {'trending_hashtags': []}
    
    # Get the current experiment from the URL or session
    experiment_identifier = request.resolver_match.kwargs.get('experiment_identifier')
    if not experiment_identifier:
        return {'trending_hashtags': []}
    
    # Create a cache key specific to this experiment
    cache_key = f'trending_hashtags_{experiment_identifier}'
    
    # Try to get cached results
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return {'trending_hashtags': cached_results}
    
    try:
        experiment = Experiment.objects.get(identifier=experiment_identifier)
        trending_hashtags = Hashtag.objects.filter(
            post__experiment=experiment
        ).values('tag').annotate(
            count=Count('id', distinct=True)
        ).order_by('-count')[:5]
        
        # Convert to a list of dictionaries with tag and count
        trending_hashtags = [{'tag': item['tag'], 'count': item['count']} for item in trending_hashtags]
        
        # Cache the results indefinitely (until invalidated by signal)
        cache.set(cache_key, trending_hashtags)
        
        return {'trending_hashtags': trending_hashtags}
    except Experiment.DoesNotExist:
        return {'trending_hashtags': []}
    except Exception as e:
        # Log the error and return empty list
        print(f"Error in trending_hashtags context processor: {str(e)}")
        return {'trending_hashtags': []}

@receiver(post_save, sender=Hashtag)
def invalidate_trending_hashtags_cache(sender, instance, **kwargs):
    """
    Signal handler that invalidates the trending hashtags cache when a new hashtag is saved.
    
    Cache Invalidation:
    - Triggered by the post_save signal from the Hashtag model
    - Gets the experiment from the post associated with the hashtag
    - Deletes the cache entry for that experiment's trending hashtags
    - This ensures the cache is always up-to-date with the latest hashtag data
    
    Note: The cache is only invalidated for the specific experiment where the hashtag was added.
    """
    # Get the experiment from the post associated with the hashtag
    if hasattr(instance, 'post') and instance.post:
        experiment = instance.post.experiment
        cache_key = f'trending_hashtags_{experiment.identifier}'
        cache.delete(cache_key)
