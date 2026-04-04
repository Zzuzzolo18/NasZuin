export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Low-level fetch wrapper that adds CSRF token and credentials.
 * Returns the raw Response — use for downloads, blobs, or streaming.
 */
export async function fetchApi(endpoint, options = {}) {
    const headers = { ...options.headers };

    const csrfToken = getCookie('csrftoken');
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }

    // Don't set Content-Type for FormData (browser sets multipart boundary)
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    return fetch(endpoint, {
        ...options,
        headers,
        credentials: 'same-origin',
    });
}

/**
 * High-level API request helper.
 * Handles CSRF, JSON parsing, and error responses automatically.
 * Skips Content-Type for FormData bodies (file uploads).
 */
export async function apiRequest(endpoint, options = {}) {
    const response = await fetchApi(endpoint, options);

    if (response.status === 204) return null;

    const text = await response.text();
    try {
        const data = JSON.parse(text);
        if (!response.ok) {
            throw new Error(data.detail || data.error || 'Something went wrong');
        }
        return data;
    } catch (e) {
        if (e.message && !e.message.includes('JSON')) throw e; // Re-throw app errors
        console.error("API Error: Response is not JSON", text.substring(0, 500));
        if (!response.ok) {
            if (response.status === 403 && text.includes("CSRF")) {
                throw new Error("CSRF Verification Failed. Please reload the page.");
            }
            throw new Error(`Server returned ${response.status} ${response.statusText}`);
        }
        throw new Error("Invalid response format from server");
    }
}
