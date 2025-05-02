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

/**
 * Makes hashtags in text content clickable by converting them to links.
 * @param {HTMLElement} container - The container element to search for text content
 * @param {Object} urls - Object containing the URLs to use
 * @param {string} urls.explore - URL for the explore page
 * @param {string} urls.exploreWithExperiment - URL for the explore page with experiment
 * @param {string} queryParam - The query parameter name to use (default: 'hashtag')
 */
function makeHashtagsClickable(container, urls, queryParam = 'hashtag') {
    // Find all elements with text content that might contain hashtags
    const textElements = container.querySelectorAll('.post-text, .comment-text, .reply-text');
    
    // Get the current experiment identifier from the URL if it exists
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    const experimentIdentifier = pathParts[0] && pathParts[0].length === 5 ? pathParts[0] : null;
    
    // Determine the base URL for hashtag links
    const exploreUrl = experimentIdentifier 
        ? urls.exploreWithExperiment.replace('0', experimentIdentifier)
        : urls.explore;
    
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
    // Get URLs from data attributes
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        const urls = {
            explore: mainContent.dataset.exploreUrl || '',
            exploreWithExperiment: mainContent.dataset.exploreWithExperimentUrl || ''
        };
        makeHashtagsClickable(mainContent, urls);
    }
    
    // Make hashtags clickable in modals
    const modals = document.querySelectorAll('.modal-content');
    modals.forEach(modal => {
        const urls = {
            explore: modal.dataset.exploreUrl || '',
            exploreWithExperiment: modal.dataset.exploreWithExperimentUrl || ''
        };
        makeHashtagsClickable(modal, urls);
    });
});
