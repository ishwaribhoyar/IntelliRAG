/**
 * IntelliRAG — Auth Service
 * 
 * Handles login, registration, and session management.
 * Keeps auth state in localStorage for persistence across page loads.
 */

const authService = {
  /**
   * Register a new user.
   * @param {string} username - Email / username
   * @param {string} password
   * @param {string} name - Display name
   */
  async register(username, password, name = '') {
    const data = await window.api.post('/register', { username, password, name });
    this._saveSession(data);
    return data;
  },

  /**
   * Login with credentials.
   * @param {string} username
   * @param {string} password
   */
  async login(username, password) {
    const data = await window.api.post('/login', { username, password });
    this._saveSession(data);
    return data;
  },

  /** Save session data to localStorage. */
  _saveSession(data) {
    if (data.user_id) {
      localStorage.setItem('user_id', data.user_id);
      localStorage.setItem('username', data.username || '');
      window.currentUserId = data.user_id;
    }
  },

  /** Get current user ID from localStorage. */
  getCurrentUserId() {
    return localStorage.getItem('user_id') || 'default_user';
  },

  /** Get current username from localStorage. */
  getCurrentUsername() {
    return localStorage.getItem('username') || 'Learner';
  },

  /** Clear session (logout). */
  logout() {
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    window.currentUserId = null;
  },

  /** Check if a user is logged in. */
  isLoggedIn() {
    return !!localStorage.getItem('user_id');
  },
};

// Make globally available
window.authService = authService;
