/**
 * Day Trader Application JS
 * Common functionality for SPA-like behavior
 */

// Save scroll position in session storage before page loads
window.addEventListener('beforeunload', function() {
  sessionStorage.setItem('scrollPosition', window.scrollY);
});

// Restore scroll position on page load
document.addEventListener('DOMContentLoaded', function() {
  // Restore scroll position if it exists
  const scrollPosition = sessionStorage.getItem('scrollPosition');
  if (scrollPosition) {
    window.scrollTo(0, parseInt(scrollPosition));
    sessionStorage.removeItem('scrollPosition'); // Clear after restoring
  }
  
  // Add AJAX form handling to all forms with data-ajax="true"
  document.querySelectorAll('form[data-ajax="true"]').forEach(form => {
    form.addEventListener('submit', handleAjaxForm);
  });
  
  // Add AJAX navigation to all links with data-ajax="true"
  document.querySelectorAll('a[data-ajax="true"]').forEach(link => {
    link.addEventListener('click', handleAjaxNavigation);
  });
});

/**
 * Handle AJAX form submissions
 */
function handleAjaxForm(e) {
  e.preventDefault();
  
  const form = e.target;
  const url = form.action;
  const method = form.method || 'POST';
  const formData = new FormData(form);
  
  fetch(url, {
    method: method,
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(data => { throw new Error(data.error || 'Unknown error occurred'); });
    }
    return response.json();
  })
  .then(data => {
    if (data.redirect) {
      window.location.href = data.redirect;
    } else if (data.success) {
      showStatusMessage(data.message || 'Operation successful', 'success');
      
      // If there's a callback function specified
      if (form.dataset.callback) {
        if (typeof window[form.dataset.callback] === 'function') {
          window[form.dataset.callback](data);
        }
      }
    }
  })
  .catch(error => {
    showStatusMessage('Error: ' + error.message, 'error');
  });
}

/**
 * Handle AJAX navigation for links
 */
function handleAjaxNavigation(e) {
  e.preventDefault();
  
  const link = e.target;
  const url = link.href;
  
  // Save current scroll position
  sessionStorage.setItem('scrollPosition', window.scrollY);
  
  // Navigate to the new URL
  window.location.href = url;
}

/**
 * Show status message
 */
function showStatusMessage(message, type) {
  // Find status message element
  let statusMessage = document.getElementById('status-message');
  
  // If not found, create one
  if (!statusMessage) {
    statusMessage = document.createElement('div');
    statusMessage.id = 'status-message';
    
    // Insert after the closest h3 or at the beginning of the main element
    const h3 = document.querySelector('h3');
    if (h3) {
      h3.parentNode.insertBefore(statusMessage, h3.nextSibling);
    } else {
      const main = document.querySelector('main');
      if (main && main.firstChild) {
        main.insertBefore(statusMessage, main.firstChild);
      }
    }
  }
  
  // Set message and class
  statusMessage.textContent = message;
  statusMessage.className = `status-${type}`;
  
  // Clear message after 3 seconds
  setTimeout(() => {
    statusMessage.textContent = '';
    statusMessage.className = '';
  }, 3000);
} 