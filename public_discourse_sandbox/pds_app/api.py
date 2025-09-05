from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status
from .models import Post, UserProfile, Experiment, Vote, Notification
from .decorators import check_banned
from .serializers import PostSerializer, UserProfileSerializer, PostCreateSerializer, ExperimentSerializer, PostReplySerializer
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
                # is_flagged will be automatically set in the save method via profanity check
            )
            # Create a notification for the parent post author
            Notification.objects.create(
                user_profile=parent_post.user_profile,
                event='post_replied',
                content=f'@{user_profile.username} replied to your post'
            )
            
            response_data = {
                'status': 'success',
                'id': str(comment.id),
                'message': 'Comment created successfully'
            }
            
            # Include flag information if the comment was flagged
            if comment.is_flagged:
                response_data['is_flagged'] = True
                
            return JsonResponse(response_data)
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
        # Also ensure the parent post is not deleted
        replies = Post.objects.filter(
            parent_post__id=post_id,
            parent_post__is_deleted=False,
            is_deleted=False  # Only show non-deleted replies
        ).select_related(
            'user_profile',
            'user_profile__user'  # Also select related user for checking banned status
        ).exclude(
            user_profile__user__groups__name='Banned'  # Exclude replies from banned users
        ).order_by('created_date')

        replies_data = [{
            'id': str(reply.id),  # Convert UUID to string
            'user_profile_id': str(reply.user_profile.id),  # Add user profile ID (not user ID)
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
            # Create a notification for the post author
            Notification.objects.create(
                user_profile=post.user_profile,
                event='post_liked',
                content=f'@{user_profile.username} liked your post'
            )
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
    Will return an error if a user attempts to repost their own content
    or if the post is already a repost.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Get the original post
        original_post = Post.objects.get(id=post_id)
        
        # Check if user is trying to repost their own post
        if original_post.user_profile.user == request.user:
            return JsonResponse({'error': 'Cannot repost your own content'}, status=403)
        
        # Check if the post is already a repost
        if original_post.repost_source is not None:
            return JsonResponse({'error': 'Reposting a repost is not allowed'}, status=403)
        
        # Get the current user's profile for the current experiment
        user_profile = UserProfile.objects.get(
            user=request.user,
            experiment=original_post.experiment
        )
        
        # Create new post with the same content
        new_post = Post.objects.create(
            user_profile=user_profile,
            experiment=original_post.experiment,
            repost_source=original_post
        )
        
        # Increment the share count on the original post
        original_post.num_shares += 1
        original_post.save(update_fields=['num_shares'])
        # Create a notification for the original post author
        Notification.objects.create(
            user_profile=original_post.user_profile,
            event='post_reposted',
            content=f'@{user_profile.username} reposted your post'
        )
        
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


# =============================================================================
# EXTERNAL API ENDPOINTS (Similar to X API)
# =============================================================================

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_home_timeline(request):
    """
    Get home timeline posts for the authenticated user.
    Similar to X's home timeline endpoint.
    
    Query Parameters:
    - experiment_id: UUID of the experiment (required)
    - max_results: Number of posts to return (default: 20, max: 100)
    - since_id: Return posts after this ID
    - until_id: Return posts before this ID
    - pagination_token: Token for pagination
    """
    try:
        # Get experiment from query parameters
        experiment_id = request.query_params.get('experiment_id')
        if not experiment_id:
            return Response({
                'error': 'experiment_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get experiment
        try:
            experiment = Experiment.objects.get(identifier=experiment_id)
        except Experiment.DoesNotExist:
            return Response({
                'error': 'Experiment not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return Response({
                'error': 'User does not have access to this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        if user_profile.is_banned:
            return Response({
                'error': 'User is banned from this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get pagination parameters
        max_results = min(int(request.query_params.get('max_results', 20)), 100)
        since_id = request.query_params.get('since_id')
        until_id = request.query_params.get('until_id')

        # Get posts using the existing get_home_feed_posts function
        from .views import get_home_feed_posts
        posts = list(get_home_feed_posts(
            request=request,
            experiment=experiment,
            page_size=max_results
        ))

        # Apply additional filters based on since_id and until_id
        if since_id:
            try:
                since_post = Post.objects.get(id=since_id)
                posts = posts.filter(created_date__gt=since_post.created_date)
            except Post.DoesNotExist:
                pass

        if until_id:
            try:
                until_post = Post.objects.get(id=until_id)
                posts = posts.filter(created_date__lt=until_post.created_date)
            except Post.DoesNotExist:
                pass

        # Serialize posts
        serializer = PostSerializer(posts, many=True, context={'request': request})

        # Prepare response data similar to X API format
        response_data = {
            'data': serializer.data,
            'meta': {
                'result_count': len(serializer.data),
                'newest_id': str(posts[0].id) if len(posts) > 0 else None,
                'oldest_id': str(posts[-1].id) if len(posts) > 0 else None,
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_search_posts(request):
    """
    Search for posts by content or hashtags.
    Similar to X's search endpoint.
    
    Query Parameters:
    - experiment_id: UUID of the experiment (required)
    - query: Search query (required)
    - max_results: Number of posts to return (default: 20, max: 100)
    - since_id: Return posts after this ID
    - until_id: Return posts before this ID
    """
    try:
        # Get experiment from query parameters
        experiment_id = request.query_params.get('experiment_id')
        if not experiment_id:
            return Response({
                'error': 'experiment_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get search query
        query = request.query_params.get('query')
        if not query:
            return Response({
                'error': 'query parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get experiment
        try:
            experiment = Experiment.objects.get(id=experiment_id)
        except Experiment.DoesNotExist:
            return Response({
                'error': 'Experiment not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return Response({
                'error': 'User does not have access to this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        if user_profile.is_banned:
            return Response({
                'error': 'User is banned from this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get pagination parameters
        max_results = min(int(request.query_params.get('max_results', 20)), 100)
        since_id = request.query_params.get('since_id')
        until_id = request.query_params.get('until_id')

        # Search posts by content or hashtags
        from django.db import models
        posts = Post.objects.filter(
            experiment=experiment,
            is_deleted=False,
            parent_post__isnull=True  # Only top-level posts
        ).filter(
            models.Q(content__icontains=query) |
            models.Q(hashtag__tag__icontains=query.lower())
        ).select_related(
            'user_profile',
            'user_profile__user'
        ).prefetch_related(
            'vote_set',
            'hashtag_set'
        ).order_by('-created_date')

        # Apply additional filters based on since_id and until_id
        if since_id:
            try:
                since_post = Post.objects.get(id=since_id)
                posts = posts.filter(created_date__gt=since_post.created_date)
            except Post.DoesNotExist:
                pass

        if until_id:
            try:
                until_post = Post.objects.get(id=until_id)
                posts = posts.filter(created_date__lt=until_post.created_date)
            except Post.DoesNotExist:
                pass

        # Limit results
        posts = posts[:max_results]

        # Add comment count and vote status
        for post in posts:
            post.comment_count = post.get_comment_count()
            post.user_has_voted = Vote.objects.filter(
                user_profile=user_profile,
                post=post,
                is_upvote=True
            ).exists()

        # Serialize posts
        serializer = PostSerializer(posts, many=True, context={'request': request})

        # Prepare response data similar to X API format
        response_data = {
            'data': serializer.data,
            'meta': {
                'result_count': len(serializer.data),
                'newest_id': str(posts[0].id) if len(posts) > 0 else None,
                'oldest_id': str(posts[-1].id) if len(posts) > 0 else None,
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_get_post(request, post_id):
    """
    Get a specific post by ID.
    Similar to X's post lookup endpoint.
    
    Path Parameters:
    - post_id: UUID of the post
    """
    try:
        # Get the post
        try:
            post = Post.objects.get(id=post_id, is_deleted=False)
        except Post.DoesNotExist:
            return Response({
                'error': 'Post not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=post.experiment).first()
        if not user_profile:
            return Response({
                'error': 'User does not have access to this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        if user_profile.is_banned:
            return Response({
                'error': 'User is banned from this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        # Add comment count and vote status
        post.comment_count = post.get_comment_count()
        post.user_has_voted = Vote.objects.filter(
            user_profile=user_profile,
            post=post,
            is_upvote=True
        ).exists()

        # Serialize post
        serializer = PostSerializer(post, context={'request': request})

        return Response({
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_create_post(request):
    """
    Create a new post.
    Similar to X's post creation endpoint.
    
    Request Body:
    - text: Post content (required, max 500 characters)
    - experiment_id: UUID of the experiment (required)
    """
    try:
        # Get experiment from request data
        experiment_id = request.data.get('experiment_id')
        if not experiment_id:
            return Response({
                'error': 'experiment_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get experiment
        try:
            experiment = Experiment.objects.get(id=experiment_id)
        except Experiment.DoesNotExist:
            return Response({
                'error': 'Experiment not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return Response({
                'error': 'User does not have access to this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        if user_profile.is_banned:
            return Response({
                'error': 'User is banned from this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        # Create post using serializer
        serializer = PostCreateSerializer(
            data=request.data,
            context={'request': request, 'experiment': experiment}
        )

        if serializer.is_valid():
            post = serializer.save()

            # Serialize the created post for response
            response_serializer = PostSerializer(post, context={'request': request})

            return Response({
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_like_post(request, post_id):
    """
    Like or unlike a post.
    Similar to X's like endpoint.
    
    Path Parameters:
    - post_id: UUID of the post
    """
    try:
        # Get the post
        try:
            post = Post.objects.get(id=post_id, is_deleted=False)
        except Post.DoesNotExist:
            return Response({
                'error': 'Post not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=post.experiment).first()
        if not user_profile:
            return Response({
                'error': 'User does not have access to this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        if user_profile.is_banned:
            return Response({
                'error': 'User is banned from this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

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
            liked = False
        else:
            # Like: create new vote and increment count
            Vote.objects.create(
                user_profile=user_profile,
                post=post,
                is_upvote=True
            )
            post.num_upvotes += 1
            post.save()
            liked = True

        return Response({
            'data': {
                'liked': liked,
                'like_count': post.num_upvotes
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_create_comment(request, post_id):
    """
    Create a comment/reply to a post.
    Similar to X's reply endpoint.
    
    Path Parameters:
    - post_id: UUID of the post to reply to
    
    Request Body:
    - text: Comment content (required, max 500 characters)
    """
    try:
        # Get the parent post
        try:
            parent_post = Post.objects.get(id=post_id, is_deleted=False)
        except Post.DoesNotExist:
            return Response({
                'error': 'Post not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if user has access to this experiment
        user_profile = request.user.userprofile_set.filter(experiment=parent_post.experiment).first()
        if not user_profile:
            return Response({
                'error': 'User does not have access to this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        if user_profile.is_banned:
            return Response({
                'error': 'User is banned from this experiment'
            }, status=status.HTTP_403_FORBIDDEN)

        # Add the parent post ID to the request data
        comment_data = request.data.copy()
        comment_data['in_reply_to_id'] = str(parent_post.id)

        # Create comment using serializer
        serializer = PostReplySerializer(
            data=comment_data,
            context={'request': request, 'experiment': parent_post.experiment}
        )

        if serializer.is_valid():
            comment = serializer.save()

            # Serialize the created comment for response
            response_serializer = PostSerializer(comment, context={'request': request})

            return Response({
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_user_experiments(request):
    """
    Get experiments that the authenticated user has access to.
    """
    try:
        # Get user's experiments
        user_profiles = request.user.userprofile_set.filter(is_banned=False)
        experiments = [profile.experiment for profile in user_profiles]

        # Serialize experiments
        serializer = ExperimentSerializer(experiments, many=True)

        return Response({
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)