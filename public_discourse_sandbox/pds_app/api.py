from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from .models import Post, UserProfile, Experiment, Vote
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
            'profile_picture': reply.user_profile.profile_picture.url if reply.user_profile.profile_picture else None,
            'is_author': reply.user_profile.user == request.user,
            'is_moderator': request.user.groups.filter(name='Moderators').exists()
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

@login_required
@ensure_csrf_cookie
@check_banned
def handle_like(request, post_id):
    """Handle post likes/unlikes."""
    try:
        post = get_object_or_404(Post, id=post_id)
        user_profile = request.user.userprofile_set.filter(experiment=post.experiment).first()
        
        if not user_profile:
            return JsonResponse({'status': 'error', 'message': 'User profile not found'}, status=404)
            
        # Check if user already voted
        existing_vote = Vote.objects.filter(
            user_profile=user_profile,
            post=post
        ).first()
        
        if existing_vote:
            # Unlike: delete the vote and decrement count
            existing_vote.delete()
            post.num_upvotes -= 1
            post.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Post unliked',
                'is_liked': False,
                'upvotes': post.num_upvotes
            })
        else:
            # Like: create new vote and increment count
            Vote.objects.create(
                user_profile=user_profile,
                post=post,
                is_upvote=True
            )
            post.num_upvotes += 1
            post.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Post liked',
                'is_liked': True,
                'upvotes': post.num_upvotes
            })
            
    except Post.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ensure_csrf_cookie
def delete_experiment(request, experiment_identifier):
    """
    Delete an experiment via AJAX/HTMX (DELETE request).
    Only the experiment creator can delete their experiment.
    Uses soft deletion by setting is_deleted to True.
    Returns JSON response (success or error), mirroring the post delete API.
    """
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        experiment = Experiment.all_objects.get(identifier=experiment_identifier)
        # Check if user is the creator
        if experiment.creator != request.user:
            return JsonResponse({'status': 'error', 'message': 'Only the experiment creator can delete this experiment'}, status=403)
        # Soft delete the experiment
        experiment.is_deleted = True
        experiment.save()
        return JsonResponse({'status': 'success', 'message': 'Experiment deleted successfully'})
    except Experiment.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Experiment not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def repost(request, post_id):
    """
    Creates a new post that copies the content of the given post.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Get the original post
        original_post = Post.objects.get(id=post_id)
        
        # Get the current user's profile for the current experiment
        user_profile = UserProfile.objects.get(
            user=request.user,
            experiment=original_post.experiment
        )
        
        # Create new post with the same content
        new_post = Post.objects.create(
            user_profile=user_profile,
            experiment=original_post.experiment,
            content=original_post.content,
        )
        
        # Increment the share count on the original post
        original_post.num_shares += 1
        original_post.save(update_fields=['num_shares'])
        
        return JsonResponse({
            'success': True,
            'post_id': str(new_post.id),
            'shares_count': original_post.num_shares
        })
    
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'User profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
