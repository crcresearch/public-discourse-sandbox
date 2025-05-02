// Helper function to make API requests with proper CSRF handling
async function makeRequest(url, method, data = null) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const headers = {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json',
    };
    
    const options = {
        method: method,
        headers: headers,
        credentials: 'same-origin'
    };
    
    if (data) {
        if (data instanceof FormData) {
            delete headers['Content-Type'];
            options.body = data;
        } else {
            options.body = JSON.stringify(data);
        }
    }
    
    const response = await fetch(url, options);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Request failed');
    }
    return response.json();
}

// Reusable function to handle follow/unfollow actions
function handleFollow(userProfileId) {
    makeRequest(
        `/api/users/${userProfileId}/follow/`,
        'POST'
    )
    .then(data => {
        if (data.status === 'success') {
            // Update the follow button state
            const followButton = document.querySelector(`button[onclick=\"handleFollow('${userProfileId}')\"]`);
            if (followButton) {
                if (data.is_following) {
                    followButton.innerHTML = '<i class="ri-user-unfollow-line"></i> Unfollow';
                } else {
                    followButton.innerHTML = '<i class="ri-user-follow-line"></i> Follow';
                }
            }
        } else {
            alert(data.message || 'An error occurred while following the user');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while following the user');
    });
}
