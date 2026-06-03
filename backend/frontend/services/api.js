/**
 * IntelliRAG — Central API Service
 * 
 * Single source of truth for all HTTP calls to the backend.
 * All page modules import from here — never use fetch() directly.
 * 
 * Usage:
 *   const result = await api.post('/ask', { user_id, query });
 *   const result = await api.get('/health');
 */

const BASE_URL = window.API_BASE_URL || '';

const api = {
  /**
   * GET request to the backend API.
   * @param {string} path - API path (e.g. '/health')
   * @param {Object} params - URL query parameters
   */
  async get(path, params = {}) {
    const url = new URL(`${BASE_URL}/api${path}`, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.append(k, v);
    });
    const res = await fetch(url.toString(), {
      headers: this._headers(),
    });
    return this._handle(res);
  },

  /**
   * POST request to the backend API.
   * @param {string} path - API path
   * @param {Object} body - JSON body
   */
  async post(path, body = {}) {
    const res = await fetch(`${BASE_URL}/api${path}`, {
      method: 'POST',
      headers: { ...this._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return this._handle(res);
  },

  /**
   * POST with FormData (file uploads).
   * @param {string} path - API path
   * @param {FormData} formData
   */
  async postForm(path, formData) {
    const res = await fetch(`${BASE_URL}/api${path}`, {
      method: 'POST',
      headers: this._headers(),
      body: formData,
    });
    return this._handle(res);
  },

  /**
   * DELETE request.
   * @param {string} path - API path
   */
  async delete(path) {
    const res = await fetch(`${BASE_URL}/api${path}`, {
      method: 'DELETE',
      headers: this._headers(),
    });
    return this._handle(res);
  },

  /** Build standard request headers. */
  _headers() {
    const headers = {};
    const userId = window.currentUserId || localStorage.getItem('user_id');
    if (userId) headers['X-User-ID'] = userId;
    return headers;
  },

  /** Parse response and throw structured errors. */
  async _handle(res) {
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        detail = err.detail || err.message || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return res.json();
    }
    return res.blob();
  },
};

// Make globally available for legacy inline handlers
window.api = api;
