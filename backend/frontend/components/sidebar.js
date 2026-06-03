/**
 * IntelliRAG — Sidebar Navigation Component
 * 
 * Manages the left sidebar: active state, mobile toggling,
 * user info display, and document quick-select.
 * Works with existing index.html sidebar markup.
 */

const sidebar = (() => {
  let _activePage = '';

  /**
   * Highlight the active nav item by page key.
   * @param {'dashboard'|'library'|'ask'|'search'|'quizzes'|'flashcards'|'weaknesses'|'uploads'} page
   */
  function setActivePage(page) {
    _activePage = page;
    document.querySelectorAll('[data-nav-page]').forEach(el => {
      const isActive = el.dataset.navPage === page;
      el.classList.toggle('active', isActive);
      el.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
  }

  /**
   * Update the user info area in the sidebar.
   * @param {{username: string, xp: number, level: number}} user
   */
  function setUser(user) {
    const nameEl = document.getElementById('sidebar-username');
    const xpEl   = document.getElementById('sidebar-xp');
    const lvlEl  = document.getElementById('sidebar-level');
    if (nameEl) nameEl.textContent = user.username || 'Learner';
    if (xpEl)   xpEl.textContent   = `${user.xp || 0} XP`;
    if (lvlEl)  lvlEl.textContent  = `Level ${user.level || 1}`;
  }

  /**
   * Populate the document selector dropdown in the sidebar.
   * @param {Array<{doc_id: string, filename: string, status: string}>} docs
   * @param {string} selectedDocId
   */
  function setDocuments(docs, selectedDocId = '') {
    const sel = document.getElementById('sidebar-doc-select');
    if (!sel) return;
    sel.innerHTML = '';

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = docs.length ? 'Select a document…' : 'No documents yet';
    sel.appendChild(placeholder);

    docs
      .filter(d => d.status === 'ready' || d.status === 'partially_ready')
      .forEach(doc => {
        const opt = document.createElement('option');
        opt.value = doc.doc_id;
        opt.textContent = _truncate(doc.filename || doc.doc_id, 36);
        opt.selected = doc.doc_id === selectedDocId;
        sel.appendChild(opt);
      });
  }

  /**
   * Toggle mobile sidebar open/close.
   */
  function toggleMobile() {
    const sb = document.getElementById('sidebar');
    if (!sb) return;
    const isOpen = sb.classList.toggle('sidebar-open');
    document.body.classList.toggle('sidebar-overlay-visible', isOpen);
  }

  /**
   * Close the sidebar (mobile).
   */
  function closeMobile() {
    const sb = document.getElementById('sidebar');
    if (sb) sb.classList.remove('sidebar-open');
    document.body.classList.remove('sidebar-overlay-visible');
  }

  /** Truncate long filenames for display. */
  function _truncate(str, maxLen) {
    return str.length <= maxLen ? str : `${str.slice(0, maxLen - 1)}…`;
  }

  // Close mobile sidebar when clicking outside
  document.addEventListener('click', (e) => {
    const sb = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    if (sb && sb.classList.contains('sidebar-open')) {
      if (!sb.contains(e.target) && e.target !== toggle) {
        closeMobile();
      }
    }
  });

  // Wire the hamburger toggle button (if present in markup)
  document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('sidebar-toggle');
    if (toggle) toggle.addEventListener('click', () => toggleMobile());
  });

  return { setActivePage, setUser, setDocuments, toggleMobile, closeMobile };
})();

window.sidebar = sidebar;
