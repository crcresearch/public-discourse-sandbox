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

/**
 * Helper function to handle form submissions with better error handling for form validation
 * @param {string} url - The API endpoint URL
 * @param {string} method - The HTTP method (POST, PUT, etc.)
 * @param {FormData|Object} data - Form data or JSON data
 * @returns {Promise<Object>} - Response data
 */
async function submitFormWithValidation(url, method, data = null) {
    try {
        // Use the existing makeRequest function
        return await makeRequest(url, method, data);
    } catch (error) {
        // Check if this is a form validation error (contains JSON error data)
        const errorMsg = error.message || '';
        
        // Try to extract and parse form validation errors
        if (errorMsg.startsWith('{') && errorMsg.endsWith('}')) {
            try {
                // Check if the error is JSON and might contain field errors
                const errorObj = JSON.parse(errorMsg);
                
                if (errorObj.error) {
                    // Try to parse the nested error object
                    const formErrors = JSON.parse(errorObj.error);
                    
                    // Format error message for display
                    let errorMessages = [];
                    
                    // Extract all error messages for each field
                    for (const field in formErrors) {
                        const fieldErrors = formErrors[field];
                        if (Array.isArray(fieldErrors)) {
                            fieldErrors.forEach(error => {
                                if (error.message) {
                                    errorMessages.push(`${field}: ${error.message}`);
                                }
                            });
                        }
                    }
                    
                    // Join all error messages
                    if (errorMessages.length) {
                        throw new Error(errorMessages.join('\n'));
                    }
                }
            } catch (parseError) {
                // JSON parsing failed, continue with original error
            }
        }
        
        // If we couldn't parse special form validation errors, just rethrow the original error
        throw error;
    }
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

/**
 * Makes hashtags in text content clickable by converting them to links.
 * @param {HTMLElement} container - The container element to search for text content
 * @param {string} baseUrl - The base URL to use for hashtag links
 * @param {string} queryParam - The query parameter name to use (default: 'hashtag')
 */
function makeHashtagsClickable(container, baseUrl = '', queryParam = 'hashtag') {
    // Find all elements with text content that might contain hashtags
    const textElements = container.querySelectorAll('.post-text, .comment-text, .reply-text');
    
    // Get the current experiment identifier from the URL if it exists
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    const experimentIdentifier = pathParts[0] && pathParts[0].length === 5 ? pathParts[0] : null;
    
    // Determine the base URL for hashtag links
    const exploreUrl = experimentIdentifier 
        ? `/${experimentIdentifier}/explore/`
        : '/explore/';
    
    textElements.forEach(element => {
        // Get the text content and preserve any existing HTML
        const text = element.innerHTML;
        
        // Replace hashtags with clickable links
        // \w+ matches word characters (letters, numbers, underscores)
        // \u00C0-\u00FF matches accented characters
        // This regex will match hashtags with international characters
        const newText = text.replace(
            /#([\w\u00C0-\u00FF]+)/g,
            `<a href="${exploreUrl}?${queryParam}=$1" class="hashtag">#$1</a>`
        );
        
        // Only update if we found hashtags to avoid unnecessary DOM updates
        if (newText !== text) {
            element.innerHTML = newText;
        }
    });
}

// Initialize hashtag clickability when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Make hashtags clickable in the main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        makeHashtagsClickable(mainContent);
    }
    
    // Make hashtags clickable in modals
    const modals = document.querySelectorAll('.modal-content');
    modals.forEach(modal => {
        makeHashtagsClickable(modal);
    });
});

document.body.addEventListener('htmx:afterSwap', function(evt) {
    // Get the container that was just updated
    const container = evt.detail.target.parentElement;
    console.log("htmx:afterSwap", container);
    if (container) {
        makeHashtagsClickable(container);
    }
});