from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from .models import Post, UserProfile

@login_required
@ensure_csrf_cookie
def create_comment(request):
    """Handle creation of comments/replies to posts."""
    # used by human users to reply to posts
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
            'username': reply.user_profile.username,
            'user_name': reply.user_profile.user.name,
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
def delete_post(request, post_id):
    """Handle deletion of posts."""
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        post = get_object_or_404(Post, id=post_id)
        
        # Check if the user owns the post
        if post.user_profile.user != request.user:
            # If not the owner, check if user has a profile in this experiment and is a moderator
            try:
                user_profile = request.user.userprofile
                if not (user_profile.experiment == post.experiment and user_profile.is_moderator):
                    print(f"User is not a moderator")
                    return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            except AttributeError as e:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
        # Soft delete the post
        post.is_deleted = True
        post.save()
        
        return JsonResponse({'status': 'success', 'message': 'Post deleted successfully'})
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
        target_profile = get_object_or_404(UserProfile, id=user_profile_id)
        
        # Check if the requesting user is a moderator in the same experiment
        try:
            mod_profile = request.user.userprofile
            if not (mod_profile.experiment == target_profile.experiment and mod_profile.is_moderator):
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        except AttributeError:
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
            mod_profile = request.user.userprofile
            if not (mod_profile.experiment == target_profile.experiment and mod_profile.is_moderator):
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        except AttributeError:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
        # Unban the user
        target_profile.is_banned = False
        target_profile.save()
        
        return JsonResponse({'status': 'success', 'message': 'User unbanned successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
