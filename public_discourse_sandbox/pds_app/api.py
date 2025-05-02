from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from .models import Post, UserProfile, Experiment
from .decorators import check_banned
import json

@login_required
@ensure_csrf_cookie
@check_banned
def create_comment(request, experiment_identifier):
    """Handle creation of comments/replies to posts."""
    # used by human users to reply to posts
    if request.method == 'POST':
        parent_id = request.POST.get('parent_post_id')
        content = request.POST.get('content')
        
        if not content:
            return JsonResponse({'status': 'error', 'message': 'Content is required'}, status=400)
            
        try:
            experiment = get_object_or_404(Experiment, identifier=experiment_identifier)
            parent_post = Post.objects.get(id=parent_id)
            user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
            
            comment = Post.objects.create(
                user_profile=user_profile,
                content=content,
                parent_post=parent_post,
                experiment=experiment,
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
# @ensure_csrf_cookie
def get_post_replies(request, post_id):
    """Get replies for a specific post."""
    try:
        # Filter replies that are not deleted and not from banned users
        replies = Post.objects.filter(
            parent_post__id=post_id,
        ).select_related(
            'user_profile',
            'user_profile__user'
        ).order_by('created_date')

        replies_data = [{
            'id': str(reply.id),  # Convert UUID to string
            'user_id': str(reply.user_profile.user.id),  # Add user ID
            'username': reply.user_profile.username,
            'display_name': reply.user_profile.display_name,
            'content': reply.content,
            'created_date': reply.created_date.isoformat(),
            'profile_picture': reply.user_profile.profile_picture.url if reply.user_profile.profile_picture else None
        } for reply in replies]
        
        return JsonResponse({'status': 'success', 'replies': replies_data})
    except Post.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ensure_csrf_cookie
@check_banned
def delete_post(request, post_id):
    """Delete a post."""
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
        
    try:
        post = get_object_or_404(Post, id=post_id)
        # Get the user's profile for this experiment
        user_profile = request.user.userprofile_set.filter(experiment=post.experiment).first()
        
        # Check if user has permission to delete (either the author or has moderator permissions)
        if (user_profile and user_profile.is_experiment_moderator()) or post.user_profile.user == request.user:
            post.is_deleted = True
            post.save()
            return JsonResponse({'status': 'success', 'message': 'Post deleted successfully'})
        else:
            return JsonResponse({'status': 'error', 'message': 'You do not have permission to delete this post'}, status=403)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ensure_csrf_cookie
def ban_user(request, user_profile_id):
    """Handle banning of users."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        # Get the target user profile
        try:
            target_profile = UserProfile.objects.get(id=user_profile_id)
        except (UserProfile.DoesNotExist, ValueError):
            return JsonResponse({'status': 'error', 'message': 'User profile not found'}, status=404)
        
        # Check if the requesting user is a moderator in the same experiment
        try:
            mod_profile = request.user.userprofile_set.get(experiment=target_profile.experiment)
            if not mod_profile.is_experiment_moderator():
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        except UserProfile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
        # Ban the user
        target_profile.is_banned = True
        target_profile.save()
        
        return JsonResponse({'status': 'success', 'message': 'User banned successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ensure_csrf_cookie
def unban_user(request, user_profile_id):
    """Handle unbanning of users."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        # Get the target user profile
        target_profile = get_object_or_404(UserProfile, id=user_profile_id)
        
        # Check if the requesting user is a moderator in the same experiment
        try:
            mod_profile = request.user.userprofile_set.get(experiment=target_profile.experiment)
            if not mod_profile.is_experiment_moderator():
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        except UserProfile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
        # Unban the user
        target_profile.is_banned = False
        target_profile.save()
        
        return JsonResponse({'status': 'success', 'message': 'User unbanned successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ensure_csrf_cookie
def update_last_accessed(request):
    """Update the user's last_accessed experiment."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        experiment_identifier = data.get('experiment_identifier')
        
        if not experiment_identifier:
            return JsonResponse({'status': 'error', 'message': 'Experiment identifier is required'}, status=400)
            
        experiment = get_object_or_404(Experiment, identifier=experiment_identifier)
        
        # Verify user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return JsonResponse({'status': 'error', 'message': 'You do not have access to this experiment'}, status=403)
            
        # Update last_accessed
        request.user.last_accessed = experiment
        request.user.save()
        
        return JsonResponse({'status': 'success', 'message': 'Last accessed experiment updated'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
