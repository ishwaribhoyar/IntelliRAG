/**
 * IntelliRAG — Dashboard Page Module
 * 
 * Manages the dashboard view: recent documents, XP score,
 * leaderboard, and quick-action buttons.
 * 
 * Usage: dashboardPage.init(userId);
 */

const dashboardPage = (() => {
  let _userId = 'default_user';

  async function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    sidebar?.setActivePage('dashboard');
    await Promise.all([
      _loadRecentDocs(),
      _loadScore(),
      _loadLeaderboard(),
    ]);
  }

  async function _loadRecentDocs() {
    const container = document.getElementById('dashboard-recent-docs');
    if (!container) return;
    try {
      loaders?.skeleton(container, 3);
      const data = await window.api.get(`/documents/${_userId}`);
      const docs = data.documents || [];
      loaders?.clearSkeleton(container);
      if (!docs.length) {
        container.innerHTML = `<p class="empty-state">No documents yet — upload one to get started!</p>`;
        return;
      }
      container.innerHTML = docs.slice(0, 6).map(doc => `
        <div class="doc-card" data-doc-id="${doc.doc_id}" onclick="selectDoc('${doc.doc_id}', '${_esc(doc.filename)}')">
          <div class="doc-card-icon">📄</div>
          <div class="doc-card-body">
            <h4 class="doc-card-title">${_esc(doc.filename || doc.doc_id)}</h4>
            <span class="doc-status ${doc.status}">${_statusLabel(doc.status)}</span>
          </div>
        </div>
      `).join('');
    } catch (e) {
      loaders?.clearSkeleton(container);
      container.innerHTML = `<p class="error-state">Failed to load documents</p>`;
    }
  }

  async function _loadScore() {
    try {
      const data = await window.api.get('/score', { user_id: _userId });
      const xpEl  = document.getElementById('dashboard-xp');
      const lvlEl = document.getElementById('dashboard-level');
      const streakEl = document.getElementById('dashboard-streak');
      if (xpEl)  xpEl.textContent  = `${data.xp || 0} XP`;
      if (lvlEl) lvlEl.textContent = `Level ${data.level || 1}`;
      if (streakEl) streakEl.textContent = `🔥 ${data.streak || 0} day streak`;
      window.sidebar?.setUser({ username: window.authService?.getCurrentUsername(), xp: data.xp, level: data.level });
    } catch (_) {}
  }

  async function _loadLeaderboard() {
    const container = document.getElementById('dashboard-leaderboard');
    if (!container) return;
    try {
      const data = await window.api.get('/leaderboard', { limit: 5 });
      const entries = data.leaderboard || [];
      container.innerHTML = entries.map((e, i) => `
        <div class="leaderboard-row ${e.user_id === _userId ? 'is-you' : ''}">
          <span class="rank">#${i + 1}</span>
          <span class="lb-user">${_esc(e.username || e.user_id)}</span>
          <span class="lb-xp">${e.daily_xp} XP</span>
        </div>
      `).join('') || '<p class="empty-state">No leaderboard data yet</p>';
    } catch (_) {}
  }

  function _statusLabel(status) {
    return { ready: '✓ Ready', processing: '⟳ Processing', failed: '✕ Failed', partially_ready: '~ Partial' }[status] || status;
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init };
})();

window.dashboardPage = dashboardPage;
