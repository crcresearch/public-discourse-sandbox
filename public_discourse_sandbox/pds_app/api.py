from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from .models import Post

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
@ensure_csrf_cookie
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
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
        # Soft delete the post
        post.is_deleted = True
        post.save()
        
        return JsonResponse({'status': 'success', 'message': 'Post deleted successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
