/**
 * IntelliRAG — Content Library Page Module
 * 
 * Manages the library view: subject list, document grid,
 * reclassify action, and document delete with confirm.
 * 
 * Usage: libraryPage.init(userId);
 */

const libraryPage = (() => {
  let _userId = 'default_user';
  let _activeSubject = '';

  function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    window.sidebar?.setActivePage('library');
    loadLibrary();
  }

  async function loadLibrary() {
    const container = document.getElementById('library-container') || document.getElementById('library-content');
    if (container) window.loaders?.skeleton(container, 3);
    try {
      const data = await window.api.get(`/library/hierarchy/${_userId}`);
      _renderHierarchy(data, container);
    } catch (err) {
      if (container) window.loaders?.clearSkeleton(container);
      window.notifications?.error('Failed to load library');
    }
  }

  function _renderHierarchy(data, container) {
    if (!container) return;
    window.loaders?.clearSkeleton(container);
    const subjects = data.subjects || [];
    if (!subjects.length) {
      container.innerHTML = `<div class="empty-state">
        <p>Your library is empty. Upload documents and they'll be classified automatically.</p>
      </div>`;
      return;
    }

    container.innerHTML = subjects.map(subj => `
      <div class="library-subject">
        <div class="subject-header" onclick="libraryPage.toggleSubject('${_esc(subj.subject)}')">
          <span class="subject-icon">📚</span>
          <span class="subject-name">${_esc(subj.subject)}</span>
          <span class="subject-count">${(subj.documents || []).length} docs</span>
          <span class="chevron" id="chevron-${_esc(subj.subject)}">▼</span>
        </div>
        <div class="subject-docs" id="docs-${_esc(subj.subject)}">
          ${(subj.documents || []).map(doc => _docCard(doc, subj.subject)).join('')}
        </div>
      </div>
    `).join('');

    if (_activeSubject) {
      document.getElementById(`docs-${_activeSubject}`)?.style.setProperty('display', 'grid');
    }
  }

  function _docCard(doc, subject) {
    return `
      <div class="lib-doc-card" data-doc-id="${doc.doc_id}">
        <div class="lib-doc-icon">📄</div>
        <div class="lib-doc-info">
          <h4 class="lib-doc-title">${_esc(doc.title || doc.doc_id)}</h4>
          <p class="lib-doc-subject">${_esc(subject)}</p>
        </div>
        <div class="lib-doc-actions">
          <button class="btn-icon" title="Open" onclick="selectDoc('${doc.doc_id}', '${_esc(doc.title)}')">📖</button>
          <button class="btn-icon btn-danger" title="Delete" onclick="libraryPage.deleteDoc('${doc.doc_id}', '${_esc(doc.title)}')">🗑</button>
        </div>
      </div>
    `;
  }

  function toggleSubject(subject) {
    const docsEl   = document.getElementById(`docs-${subject}`);
    const chevron  = document.getElementById(`chevron-${subject}`);
    if (!docsEl) return;
    const isOpen = docsEl.style.display !== 'none' && docsEl.style.display !== '';
    docsEl.style.display   = isOpen ? 'none' : 'grid';
    if (chevron) chevron.textContent = isOpen ? '▶' : '▼';
    _activeSubject = isOpen ? '' : subject;
  }

  async function deleteDoc(docId, filename) {
    const ok = await window.modals?.confirm(
      `Permanently delete "${filename}"? All indexes, quiz history, and data will be removed.`,
      'Delete', 'Cancel'
    );
    if (!ok) return;

    const toastId = window.notifications?.loading('Deleting document…');
    try {
      await window.api.delete(`/doc/${docId}`);
      window.notifications?.dismiss(toastId);
      window.notifications?.success('Document deleted');
      loadLibrary();
    } catch (err) {
      window.notifications?.dismiss(toastId);
      window.notifications?.error(err.message || 'Delete failed');
    }
  }

  async function reclassify() {
    const ok = await window.modals?.confirm('Re-classify all documents using AI? This may take a moment.', 'Reclassify');
    if (!ok) return;
    const toastId = window.notifications?.loading('Reclassifying…');
    try {
      await window.api.post('/library/reclassify', { user_id: _userId });
      window.notifications?.dismiss(toastId);
      window.notifications?.success('Library reclassified!');
      loadLibrary();
    } catch (err) {
      window.notifications?.dismiss(toastId);
      window.notifications?.error(err.message || 'Reclassify failed');
    }
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init, loadLibrary, toggleSubject, deleteDoc, reclassify };
})();

window.libraryPage = libraryPage;
