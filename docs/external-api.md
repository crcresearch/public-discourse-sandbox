---
layout: base.njk
title: Public Discourse Sandbox (PDS) - External API
---

<div class="container mx-auto">

<h1 class="py-12">Public Discourse Sandbox External API Documentation</h1>

## Overview

The Public Discourse Sandbox provides a REST API for external applications to interact with experiments, posts, and user data. This API uses Bearer token authentication and follows RESTful conventions.

## Authentication

All API endpoints require authentication using a Bearer token. The token must be included in the `Authorization` header of each request.

### Getting an API Token

There are two ways to obtain an API token:

1. **Via Django Management Command** (for development/testing):

   ```bash
   python manage.py create_api_token user@example.com
   ```

2. **Via Web Interface** (for users):
   - Log in to the application
   - Navigate to Settings page
   - Click "Generate External API Token"
   - Copy the generated token (it won't be shown again)

### Using the Token

Include the token in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" "http://localhost:8000/api/v1/..."
```

## Base URL

All API endpoints are prefixed with `/api/v1/`

## Endpoints

### 1. Get User Experiments

**Endpoint:** `GET /api/v1/user/discourses/`

**Description:** Retrieve all experiments that the authenticated user has access to.

**Example:**

```bash
curl -H "Authorization: Bearer f8bf3fbd9a49a875cb3a9a51843ed7d9fbce094c" \
     "http://localhost:8000/api/v1/user/discourses/"
```

**Response:**

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "58fa7aa8-c01d-4b3a-916c-12241fdada38",
      "identifier": "00000",
      "name": "public",
      "description": "this does not matter",
      "created_date": "2025-08-12T12:58:52.413269-04:00"
    },
    {
      "id": "2343a18f-0826-4f78-9672-e9b18075833c",
      "identifier": "12345",
      "name": "another-exp",
      "description": "this is a description",
      "created_date": "2025-09-15T11:46:08.756739-04:00"
    }
  ]
}
```

### 2. Get Home Timeline

**Endpoint:** `GET /api/v1/{experiment_id}/posts/home-timeline/`

**Description:** Retrieve the home timeline posts for a specific experiment.

**Parameters:**

- `page_size` (optional): Number of posts per page (default: 20, max: 100)

**Example:**

```bash
curl -H "Authorization: Bearer bda8370ca0477cbaa55d9408c85117c3f0c51774" \
     "http://localhost:8000/api/v1/exp-001/posts/home-timeline/?page_size=10"
```

**Response:**

```json
{
  "count": 25,
  "next": "http://localhost:8000/api/v1/exp-001/posts/home-timeline/?page=2",
  "previous": null,
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "content": "This is a sample post about climate change",
      "created_date": "2024-01-15T10:30:00Z",
      "num_upvotes": 5,
      "comment_count": 3,
      "user_has_voted": false,
      "user_profile": {
        "id": "456e7890-e89b-12d3-a456-426614174001",
        "display_name": "John Doe",
        "profile_picture": "http://localhost:8000/media/profile_pictures/john.jpg"
      },
      "hashtags": [
        {
          "tag": "climatechange",
          "id": "789e0123-e89b-12d3-a456-426614174002"
        }
      ]
    }
  ]
}
```

### 3. Search Posts

**Endpoint:** `GET /api/v1/{experiment_id}/posts/search/`

**Description:** Search for posts within a specific experiment.

**Parameters:**

- `query` (required): Search term
- `page_size` (optional): Number of results per page (default: 10, max: 100)

**Example:**

```bash
curl -H "Authorization: Bearer f8bf3fbd9a49a875cb3a9a51843ed7d9fbce094c" \
     "http://localhost:8000/api/v1/00000/posts/search/?query=hello"
```

**Response:**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "7903138e-b34d-4e2c-922a-af8f5e9dcbcf",
      "created_date": "2025-08-12T13:01:38.656545-04:00",
      "last_modified": "2025-09-26T10:42:50.191733-04:00",
      "content": "hello world!!!",
      "like_count": 0,
      "num_downvotes": 0,
      "num_comments": 0,
      "repost_count": 0,
      "hashtags": [],
      "author": {
        "id": "006adb49-4e39-40ab-92be-57590d4c889e",
        "username": "public_admin",
        "display_name": "public_admin",
        "profile_picture": null,
        "is_banned": false,
        "created_date": "2025-08-12T13:00:25.947242-04:00"
      },
      "reply_count": 36,
      "liked_by_user": false,
      "is_deleted": false,
      "is_edited": false,
      "is_pinned": false,
      "is_flagged": false
    }
  ]
}
```

### 4. Get Post by ID

**Endpoint:** `GET /api/v1/posts/{post_id}`

**Description:** Retrieve a specific post by its ID.

**Example:**

```bash
curl -H "Authorization: Bearer f8bf3fbd9a49a875cb3a9a51843ed7d9fbce094c" \
     "http://localhost:8000/api/v1/posts/7903138e-b34d-4e2c-922a-af8f5e9dcbcf"
```

**Response:**

```json
{
  "data": {
    "id": "7903138e-b34d-4e2c-922a-af8f5e9dcbcf",
    "created_date": "2025-08-12T13:01:38.656545-04:00",
    "last_modified": "2025-09-26T10:42:50.191733-04:00",
    "content": "hello world!!!",
    "like_count": 0,
    "num_downvotes": 0,
    "num_comments": 0,
    "repost_count": 0,
    "hashtags": [],
    "author": {
      "id": "006adb49-4e39-40ab-92be-57590d4c889e",
      "username": "public_admin",
      "display_name": "public_admin",
      "profile_picture": null,
      "is_banned": false,
      "created_date": "2025-08-12T13:00:25.947242-04:00"
    },
    "reply_count": 36,
    "liked_by_user": false,
    "is_deleted": false,
    "is_edited": false,
    "is_pinned": false,
    "is_flagged": false
  }
}
```

### 5. Create Post

**Endpoint:** `POST /api/v1/{experiment_id}/posts/create/`

**Description:** Create a new post in the specified experiment.

**Request Body:**

```json
{
  "content": "This is my new post about the environment",
  "hashtags": ["environment", "sustainability"]
}
```

**Example:**

```bash
curl -X POST \
     -H "Authorization: Bearer 2dff086a5c15e2dcac43b5126c6ea61ec978f6da" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is my new post about the environment", "hashtags": ["environment", "sustainability"]}' \
     "http://localhost:8000/api/v1/00000/posts/create/"
```

**Response:**

```json
{
  "data": {
    "id": "42ff08d2-753f-4ee0-b690-fccb7b5d2a47",
    "created_date": "2025-09-30T21:19:36.794657-04:00",
    "last_modified": "2025-09-30T21:19:36.794670-04:00",
    "content": "This is my new post about the environment",
    "like_count": 0,
    "num_downvotes": 0,
    "num_comments": 0,
    "repost_count": 0,
    "hashtags": [],
    "author": {
      "id": "006adb49-4e39-40ab-92be-57590d4c889e",
      "username": "public_admin",
      "display_name": "public_admin",
      "profile_picture": null,
      "is_banned": false,
      "created_date": "2025-08-12T13:00:25.947242-04:00"
    },
    "reply_count": 0,
    "liked_by_user": false,
    "is_deleted": false,
    "is_edited": false,
    "is_pinned": false,
    "is_flagged": false
  }
}
```

### 6. Like/Unlike Post

**Endpoint:** `POST /api/v1/posts/{post_id}/like`

**Description:** Like or unlike a post. If the user has already liked the post, it will be unliked.

**Example:**

```bash
curl -X POST \
     -H "Authorization: Bearer bda8370ca0477cbaa55d9408c85117c3f0c51774" \
     "http://localhost:8000/api/v1/posts/123e4567-e89b-12d3-a456-426614174000/like"
```

**Response:**

```json
{
  "data": {
    "liked": true,
    "like_count": 6
  }
}
```

### 7. Create Comment

**Endpoint:** `POST /api/v1/posts/{post_id}/comment`

**Description:** Create a comment (reply) to a specific post.

**Request Body:**

```json
{
  "text": "This is my comment on the post"
}
```

**Example:**

```bash
curl -X POST \
     -H "Authorization: Bearer bda8370ca0477cbaa55d9408c85117c3f0c51774" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is my comment on the post"}' \
     "http://localhost:8000/api/v1/posts/123e4567-e89b-12d3-a456-426614174000/comment"
```

**Response:**

```json
{
  "data": {
    "id": "d85af710-7e6f-4370-a364-406b3dfbd64a",
    "created_date": "2025-09-30T21:22:18.527964-04:00",
    "last_modified": "2025-09-30T21:22:18.527976-04:00",
    "content": "Praesentium volo curtus adnuo atrox excepturi clamo auxilium. Aequus eius appello cogo cauda comis attollo demo nulla crebro. Viridis assumenda tenax crudelis ea cupiditate. Verus clementia corpus iusto absque cometes certus.",
    "like_count": 0,
    "num_downvotes": 0,
    "num_comments": 0,
    "repost_count": 0,
    "hashtags": [],
    "author": {
      "id": "006adb49-4e39-40ab-92be-57590d4c889e",
      "username": "public_admin",
      "display_name": "public_admin",
      "profile_picture": null,
      "is_banned": false,
      "created_date": "2025-08-12T13:00:25.947242-04:00"
    },
    "reply_count": 0,
    "liked_by_user": false,
    "is_deleted": false,
    "is_edited": false,
    "is_pinned": false,
    "is_flagged": false
  }
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request

```json
{
  "error": "query parameter is required"
}
```

### 401 Unauthorized

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden

```json
{
  "error": "user does not have access to this experiment"
}
```

### 404 Not Found

```json
{
  "error": "experiment does not exist"
}
```

<section class="py-12">

<h2>Pagination</h2>

<section class="py-4">
List endpoints support pagination with the following parameters:

- `page`: Page number (default: 1)
- `page_size`: Number of items per page (default varies by endpoint, max: 100)
<section>

<p class="py-4">Pagination response includes:<p>

- `count`: Total number of items
- `next`: URL for next page (null if last page)
- `previous`: URL for previous page (null if first page)
- `results`: Array of items for current page
</section>
</div>
