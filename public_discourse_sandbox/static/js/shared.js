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
        const response = await makeRequest(`/api/users/${userProfileId}/ban/`, 'POST');
        if (response.status === 'success') {
            showToast('success', 'User has been banned successfully');
            window.location.reload();
        } else {
            showToast('error', response.message || 'Failed to ban user');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('error', error.message || 'An error occurred while banning the user');
    }
}

// Function to unban a user
async function unbanUser(userProfileId) {
    if (!confirm('Are you sure you want to unban this user?')) {
        return;
    }
    
    try {
        const response = await makeRequest(`/api/users/${userProfileId}/unban/`, 'POST');
        if (response.status === 'success') {
            showToast('success', 'User has been unbanned successfully');
            window.location.reload();
        } else {
            showToast('error', response.message || 'Failed to unban user');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('error', error.message || 'An error occurred while unbanning the user');
    }
} 