/* Alexandria RAG - Shared JavaScript */

// API Helper
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };

    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(endpoint, options);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `HTTP ${response.status}`);
    }

    return await response.json();
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(isoString) {
    if (!isoString) return 'Never';
    return new Date(isoString).toLocaleString();
}

// Notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <p>${escapeHtml(message)}</p>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    document.body.appendChild(notification);

    setTimeout(() => notification.remove(), 5000);
}

// Add notification styles if not already there
if (!document.querySelector('style[data-notifications]')) {
    const style = document.createElement('style');
    style.setAttribute('data-notifications', 'true');
    style.textContent = `
        .notification {
            position: fixed;
            top: 1rem;
            right: 1rem;
            padding: 1rem;
            border-radius: 6px;
            background: white;
            border-left: 4px solid #2196F3;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            max-width: 400px;
            z-index: 9999;
            animation: slideIn 0.3s ease;
        }

        .notification p {
            margin: 0;
        }

        .notification button {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: #999;
        }

        .notification-success {
            border-left-color: #4CAF50;
        }

        .notification-error {
            border-left-color: #f44336;
        }

        .notification-warning {
            border-left-color: #FFA500;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @media (max-width: 768px) {
            .notification {
                right: 0.5rem;
                left: 0.5rem;
                max-width: none;
            }
        }
    `;
    document.head.appendChild(style);
}

// Debug Helper
function debug(message, data = null) {
    if (typeof console !== 'undefined') {
        console.log('[Alexandria RAG]', message, data || '');
    }
}

// Export for use in templates
window.apiCall = apiCall;
window.escapeHtml = escapeHtml;
window.formatBytes = formatBytes;
window.formatDate = formatDate;
window.showNotification = showNotification;
window.debug = debug;
