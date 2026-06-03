/**
 * IntelliRAG — Search Service
 * 
 * Handles all search-related API calls: keyword, hybrid, AI modes,
 * autocomplete suggestions, and user-scoped search.
 */

const searchService = {
  /**
   * Search within a specific document.
   * @param {string} docId
   * @param {string} query
   * @param {string} mode - 'keyword' | 'hybrid' | 'ai' | 'auto'
   * @param {string} userId
   */
  async search(docId, query, mode = 'auto', userId = 'default_user') {
    return window.api.post('/search', { doc_id: docId, query, mode, user_id: userId });
  },

  /**
   * Search across all user's documents.
   * @param {string} userId
   * @param {string} query
   * @param {string} mode
   * @param {number} limit
   */
  async searchAll(userId, query, mode = 'hybrid', limit = 20) {
    return window.api.post('/search/user', { user_id: userId, query, mode, limit });
  },

  /**
   * Get autocomplete suggestions for a document.
   * @param {string} docId
   * @param {string} q - partial query
   * @param {number} limit
   */
  async suggest(docId, q, limit = 8) {
    return window.api.get(`/search/suggest/${encodeURIComponent(docId)}`, { q, limit });
  },

  /**
   * Get user-scoped autocomplete suggestions.
   * @param {string} userId
   * @param {string} q
   * @param {number} limit
   */
  async suggestForUser(userId, q, limit = 5) {
    return window.api.get(`/search/suggest/user/${encodeURIComponent(userId)}`, { q, limit });
  },

  /**
   * Get chunks for a specific hierarchy node.
   * @param {string} docId
   * @param {string} nodeId
   * @param {string} userId
   */
  async getNodeChunks(docId, nodeId, userId = 'default_user') {
    return window.api.get(`/node_chunks/${encodeURIComponent(docId)}/${encodeURIComponent(nodeId)}`, { user_id: userId });
  },
};

// Make globally available
window.searchService = searchService;
