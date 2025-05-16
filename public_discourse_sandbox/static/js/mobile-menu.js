// Simple mobile menu functionality
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const closeMenuBtn = document.getElementById('close-mobile-menu');
    const mobileMenuPanel = document.getElementById('mobile-menu-panel');
    const mobileMenuContent = document.getElementById('mobile-menu-content');
    
    // Create overlay element for background
    const overlay = document.createElement('div');
    overlay.className = 'mobile-overlay';
    document.body.appendChild(overlay);
    
    // Function to open mobile menu
    function openMobileMenu() {
        // Clone left sidebar navigation to mobile menu
        const leftNav = document.querySelector('.left-sidebar .nav-menu');
        if (leftNav && mobileMenuContent) {
            mobileMenuContent.innerHTML = '';
            mobileMenuContent.appendChild(leftNav.cloneNode(true));
            
            // Add experiment selector if available
            const experimentDropdown = document.querySelector('.trending-section select#experiment-dropdown');
            if (experimentDropdown) {
                const expSelectDiv = document.createElement('div');
                expSelectDiv.className = 'mobile-experiment-select';
                
                const heading = document.createElement('h4');
                heading.textContent = 'Discourses';
                
                const selectClone = experimentDropdown.cloneNode(true);
                selectClone.id = 'mobile-experiment-dropdown';
                
                // Add event listener to the cloned dropdown
                selectClone.addEventListener('change', function() {
                    experimentDropdown.value = this.value;
                    const changeEvent = new Event('change');
                    experimentDropdown.dispatchEvent(changeEvent);
                });
                
                expSelectDiv.appendChild(heading);
                expSelectDiv.appendChild(selectClone);
                
                // Add to beginning of menu content
                if (mobileMenuContent.firstChild) {
                    mobileMenuContent.insertBefore(expSelectDiv, mobileMenuContent.firstChild);
                } else {
                    mobileMenuContent.appendChild(expSelectDiv);
                }
            }
        }
        
        // Show menu and overlay
        mobileMenuPanel.classList.add('active');
        overlay.style.display = 'block';
        document.body.style.overflow = 'hidden'; // Prevent scrolling
    }
    
    // Function to close mobile menu
    function closeMobileMenu() {
        mobileMenuPanel.classList.remove('active');
        overlay.style.display = 'none';
        document.body.style.overflow = ''; // Restore scrolling
    }
    
    // Event listeners
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', openMobileMenu);
    }
    
    if (closeMenuBtn) {
        closeMenuBtn.addEventListener('click', closeMobileMenu);
    }
    
    // Close when clicking overlay
    overlay.addEventListener('click', closeMobileMenu);
    
    // Close when clicking a link in the menu
    if (mobileMenuContent) {
        mobileMenuContent.addEventListener('click', function(e) {
            if (e.target.tagName === 'A') {
                closeMobileMenu();
            }
        });
    }
}); 