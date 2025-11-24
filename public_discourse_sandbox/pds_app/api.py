import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie

from .decorators import check_banned
from .models import Experiment
from .models import Notification
from .models import Post
from .models import UserProfile
from .models import Vote
from .utils import send_notification_to_user


@login_required
@ensure_csrf_cookie
@check_banned
def create_comment(request, experiment_identifier):
    """Handle creation of comments/replies to posts."""
    # used by human users to reply to posts
    if request.method == "POST":
        parent_id = request.POST.get("parent_post_id")
        content = request.POST.get("content")

        if not content:
            return JsonResponse(
                {"status": "error", "message": "Content is required"},
                status=400,
            )

        try:
            experiment = get_object_or_404(Experiment, identifier=experiment_identifier)
            parent_post = Post.objects.get(id=parent_id)
            user_profile = request.user.userprofile_set.filter(
                experiment=experiment,
            ).first()

            comment = Post.objects.create(
                user_profile=user_profile,
                content=content,
                parent_post=parent_post,
                experiment=experiment,
                depth=parent_post.depth + 1,
                # is_flagged will be automatically set in the save method via profanity check
            )

            parent_post.num_comments += 1
            parent_post.save()

            if parent_post.user_profile.username != user_profile.username:
                # Create a notification for the parent post author
                post_url = f"{request.build_absolute_uri().rsplit("/",2)[0]}/post/{parent_id.id}"

                Notification.objects.create(
                    user_profile=parent_post.user_profile,
                    event="post_replied",
                    content=f"@{user_profile.username} replied to your post",
                )
                send_notification_to_user(
                    user_profile=parent_post.user_profile,
                    title="Public Discourse Notification",
                    body=f"@{user_profile.username} replied to your post {post_url}",
                )

            response_data = {
                "status": "success",
                "id": str(comment.id),
                "message": "Comment created successfully",
            }

            # Include flag information if the comment was flagged
            if comment.is_flagged:
                response_data["is_flagged"] = "true"

            return JsonResponse(response_data)
        except Post.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Parent post not found"},
                status=404,
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse(
        {"status": "error", "message": "Method not allowed"},
        status=405,
    )


@login_required
def get_post_replies(request, post_id):
    """
    Return a fully nested reply tree for a post, using each reply's `depth`
    to build the hierarchy. Excludes deleted posts and posts from "Banned" users.
    If a parent is excluded, its whole subtree is excluded as well.
    """
    try:
        from django.db.models import Q

        # Ensure root exists and isn't deleted
        root = Post.objects.only("id", "is_deleted", "depth").get(id=post_id)
        if root.is_deleted:
            return JsonResponse({"status": "success", "replies": []})

        # Base filters enforced at *every* level
        base_filters = Q(is_deleted=False) & Q(parent_post__is_deleted=False)

        # Collect descendants iteratively (BFS) starting from direct children.
        # We do this to avoid requiring a "thread_root" or tree extension.
        level = list(
            Post.objects.filter(base_filters, parent_post_id=root.id)
            .select_related("user_profile", "user_profile__user")
            .exclude(user_profile__user__groups__name="Banned"),
        )

        all_replies = level[:]

        while level:
            parent_ids = [r.id for r in level]
            level = list(
                Post.objects.filter(base_filters, parent_post_id__in=parent_ids)
                .select_related("user_profile", "user_profile__user")
                .exclude(user_profile__user__groups__name="Banned"),
            )
            all_replies.extend(level)

        if not all_replies:
            return JsonResponse({"status": "success", "replies": []})

        all_replies.sort(key=lambda r: (getattr(r, "depth", 0), r.created_date))

        is_moderator = request.user.groups.filter(name="Moderators").exists()

        def serialize(reply):
            return {
                "id": str(reply.id),
                "user_profile_id": str(reply.user_profile.id),
                "username": reply.user_profile.username,
                "display_name": reply.user_profile.display_name,
                "content": reply.content,
                "num_upvotes": reply.num_upvotes,
                "num_shares": reply.num_shares,
                "created_date": reply.created_date.isoformat(),
                "profile_picture": reply.user_profile.profile_picture.url
                if getattr(reply.user_profile, "profile_picture", None)
                else None,
                "is_author": reply.user_profile.user == request.user,
                "is_moderator": is_moderator,
                "depth": int(getattr(reply, "depth", 0)),
                "replies": [],
            }

        # Build nodes in depth order so parents exist before children
        node_by_id = {}
        top_level = []

        for r in all_replies:
            node = serialize(r)
            node_by_id[r.id] = node

            # Attach to parent; if parent is the root post, put in top_level
            if r.parent_post_id == root.id:
                top_level.append(node)
            else:
                parent_node = node_by_id.get(r.parent_post_id)
                # If the parent was filtered out (deleted/banned), drop this subtree
                if parent_node is not None:
                    parent_node["replies"].append(node)

        # Ensure children under each parent are ordered by created_date (already stable,
        # but enforce explicitly if needed)
        def sort_children(n):
            n["replies"].sort(key=lambda ch: ch["created_date"])
            for ch in n["replies"]:
                sort_children(ch)

        for n in top_level:
            sort_children(n)

        return JsonResponse({"status": "success", "replies": top_level})

    except Post.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Post not found"},
            status=404,
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@ensure_csrf_cookie
@check_banned
def delete_post(request, post_id):
    """Delete a post."""
    if request.method != "DELETE":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"},
            status=405,
        )

    try:
        post = get_object_or_404(Post, id=post_id)
        # Get the user's profile for this experiment
        user_profile = request.user.userprofile_set.filter(
            experiment=post.experiment,
        ).first()

        # Check if user has permission to delete (either the author or has moderator permissions)
        if (
            user_profile and user_profile.is_experiment_moderator()
        ) or post.user_profile.user == request.user:
            post.is_deleted = True
            post.save()
            return JsonResponse(
                {"status": "success", "message": "Post deleted successfully"},
            )
        return JsonResponse(
            {
                "status": "error",
                "message": "You do not have permission to delete this post",
            },
            status=403,
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def ban_user(request, user_profile_id):
    """Handle banning of users."""
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"},
            status=405,
        )

    try:
        # Get the target user profile
        try:
            target_profile = UserProfile.objects.get(id=user_profile_id)
        except (UserProfile.DoesNotExist, ValueError):
            return JsonResponse(
                {"status": "error", "message": "User profile not found"},
                status=404,
            )

        # Check if the requesting user is a moderator in the same experiment
        try:
            mod_profile = request.user.userprofile_set.get(
                experiment=target_profile.experiment,
            )
            if not mod_profile.is_experiment_moderator():
                return JsonResponse(
                    {"status": "error", "message": "Unauthorized"},
                    status=403,
                )
        except UserProfile.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Unauthorized"},
                status=403,
            )

        # Ban the user
        target_profile.is_banned = True
        target_profile.save()

        return JsonResponse(
            {"status": "success", "message": "User banned successfully"},
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def unban_user(request, user_profile_id):
    """Handle unbanning of users."""
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"},
            status=405,
        )

    try:
        # Get the target user profile
        target_profile = get_object_or_404(UserProfile, id=user_profile_id)

        # Check if the requesting user is a moderator in the same experiment
        try:
            mod_profile = request.user.userprofile_set.get(
                experiment=target_profile.experiment,
            )
            if not mod_profile.is_experiment_moderator():
                return JsonResponse(
                    {"status": "error", "message": "Unauthorized"},
                    status=403,
                )
        except UserProfile.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Unauthorized"},
                status=403,
            )

        # Unban the user
        target_profile.is_banned = False
        target_profile.save()

        return JsonResponse(
            {"status": "success", "message": "User unbanned successfully"},
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def update_last_accessed(request):
    """Update the user's last_accessed experiment."""
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"},
            status=405,
        )

    try:
        data = json.loads(request.body)
        experiment_identifier = data.get("experiment_identifier")

        if not experiment_identifier:
            return JsonResponse(
                {"status": "error", "message": "Experiment identifier is required"},
                status=400,
            )

        experiment = get_object_or_404(Experiment, identifier=experiment_identifier)

        # Verify user has access to this experiment
        user_profile = request.user.userprofile_set.filter(
            experiment=experiment,
        ).first()
        if not user_profile:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "You do not have access to this experiment",
                },
                status=403,
            )

        # Update last_accessed
        request.user.last_accessed = experiment
        request.user.save()

        return JsonResponse(
            {"status": "success", "message": "Last accessed experiment updated"},
        )
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@ensure_csrf_cookie
@check_banned
def handle_like(request, post_id):
    """Handle post likes/unlikes."""
    try:
        post = get_object_or_404(Post, id=post_id)
        user_profile = request.user.userprofile_set.filter(
            experiment=post.experiment,
        ).first()

        if not user_profile:
            return JsonResponse(
                {"status": "error", "message": "User profile not found"},
                status=404,
            )

        # Check if user already voted
        existing_vote = Vote.objects.filter(
            user_profile=user_profile,
            post=post,
        ).first()

        if existing_vote:
            # Unlike: delete the vote and decrement count
            existing_vote.delete()
            post.num_upvotes -= 1
            post.save()
            return JsonResponse(
                {
                    "status": "success",
                    "message": "Post unliked",
                    "is_liked": False,
                    "upvotes": post.num_upvotes,
                },
            )
        # Like: create new vote and increment count
        Vote.objects.create(user_profile=user_profile, post=post, is_upvote=True)
        post.num_upvotes += 1
        post.save()
        # Create a notification for the post author
        if user_profile.username != post.user_profile.username:
            Notification.objects.create(
                user_profile=post.user_profile,
                event="post_liked",
                content=f"@{user_profile.username} liked your post",
            )
            post_url = f"{request.build_absolute_uri().rsplit("/",4)[0]}/{post.experiment.identifier}/post/{post.id}"

            send_notification_to_user(
                user_profile=post.user_profile,
                title="Public Discourse Notification",
                body=f"@{user_profile.username} liked to your post {post_url}",
            )
        return JsonResponse(
            {
                "status": "success",
                "message": "Post liked",
                "is_liked": True,
                "upvotes": post.num_upvotes,
            },
        )

    except Post.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Post not found"},
            status=404,
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def delete_experiment(request, experiment_identifier):
    """
    Delete an experiment via AJAX/HTMX (DELETE request).
    Only the experiment creator can delete their experiment.
    Uses soft deletion by setting is_deleted to True.
    Returns JSON response (success or error), mirroring the post delete API.
    """
    if request.method != "DELETE":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"},
            status=405,
        )
    try:
        experiment = Experiment.all_objects.get(identifier=experiment_identifier)
        # Check if user is the creator
        if experiment.creator != request.user:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Only the experiment creator can delete this experiment",
                },
                status=403,
            )
        # Soft delete the experiment
        experiment.is_deleted = True
        experiment.save()
        return JsonResponse(
            {"status": "success", "message": "Experiment deleted successfully"},
        )
    except Experiment.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Experiment not found."},
            status=404,
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def repost(request, post_id):
    """
    Creates a new post that copies the content of the given post.
    Will return an error if a user attempts to repost their own content
    or if the post is already a repost.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Get the original post
        original_post = Post.objects.get(id=post_id)

        # Check if user is trying to repost their own post
        if original_post.user_profile.user == request.user:
            return JsonResponse({"error": "Cannot repost your own content"}, status=403)

        # Check if the post is already a repost
        if original_post.repost_source is not None:
            return JsonResponse(
                {"error": "Reposting a repost is not allowed"},
                status=403,
            )

        # Get the current user's profile for the current experiment
        user_profile = UserProfile.objects.get(
            user=request.user,
            experiment=original_post.experiment,
        )

        # Create new post with the same content
        new_post = Post.objects.create(
            user_profile=user_profile,
            experiment=original_post.experiment,
            repost_source=original_post,
        )

        # Increment the share count on the original post
        original_post.num_shares += 1
        original_post.save(update_fields=["num_shares"])
        # Create a notification for the original post author
        Notification.objects.create(
            user_profile=original_post.user_profile,
            event="post_reposted",
            content=f"@{user_profile.username} reposted your post",
        )
        post_url = f"{request.build_absolute_uri().rsplit("/",2)[0]}/post/{original_post.id}"
        send_notification_to_user(
            user_profile=original_post.user_profile,
            title="Public Discourse Notification",
            body=f"@{user_profile.username} reposted to your post {post_url}",
        )

        return JsonResponse(
            {
                "success": True,
                "post_id": str(new_post.id),
                "shares_count": original_post.num_shares,
            },
        )

    except Post.DoesNotExist:
        return JsonResponse({"error": "Post not found"}, status=404)
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "User profile not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
