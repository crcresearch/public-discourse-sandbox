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

// Function to ban a user
async function banUser(userProfileId) {
    if (!confirm('Are you sure you want to ban this user?')) {
        return;
    }
    
    try {
        await makeRequest(`/api/users/${userProfileId}/ban/`, 'POST');
        // Refresh the page to reflect the changes
        window.location.reload();
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'Failed to ban user');
    }
} 