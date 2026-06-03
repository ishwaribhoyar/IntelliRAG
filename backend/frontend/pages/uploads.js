/**
 * IntelliRAG — Uploads Page Module
 * 
 * Manages the upload view: drag-and-drop, multi-file queue,
 * per-file progress polling, retry failed docs.
 * 
 * Usage: uploadsPage.init(userId);
 */

const uploadsPage = (() => {
  let _userId = 'default_user';
  let _pollingIntervals = {};

  function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    window.sidebar?.setActivePage('uploads');
    _bindEvents();
    loadDocumentList();
  }

  function _bindEvents() {
    // File input
    const input = document.getElementById('upload-file-input');
    if (input) input.addEventListener('change', e => _handleFiles(e.target.files));

    // Drop zone
    const zone = document.getElementById('upload-drop-zone');
    if (zone) {
      zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
      zone.addEventListener('dragleave', ()  => zone.classList.remove('drag-over'));
      zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        _handleFiles(e.dataTransfer.files);
      });
      zone.addEventListener('click', () => input?.click());
    }
  }

  async function _handleFiles(files) {
    if (!files?.length) return;

    const formData = new FormData();
    for (const file of files) formData.append('files[]', file);
    formData.append('user_id', _userId);

    const toastId = window.notifications?.loading(`Uploading ${files.length} file(s)…`);
    try {
      const data = await window.api.postForm('/upload/multi', formData);
      window.notifications?.dismiss(toastId);

      const accepted = data.accepted_files || data.accepted || [];
      const rejected = data.rejected_files || data.rejected || [];

      if (accepted.length) {
        window.notifications?.success(`${accepted.length} file(s) accepted for processing`);
        accepted.forEach(doc => { if (!doc.duplicate) _startPolling(doc.doc_id); });
      }
      if (rejected.length) {
        window.notifications?.error(`${rejected.length} file(s) rejected: ${rejected.map(r => r.error).join(', ')}`);
      }
      loadDocumentList();
    } catch (err) {
      window.notifications?.dismiss(toastId);
      window.notifications?.error(err.message || 'Upload failed');
    }
  }

  async function loadDocumentList() {
    const container = document.getElementById('uploads-doc-list');
    if (!container) return;
    try {
      const data = await window.api.get(`/documents/${_userId}`);
      _renderDocList(data.documents || [], container);
    } catch (_) {}
  }

  function _renderDocList(docs, container) {
    if (!docs.length) {
      container.innerHTML = `<div class="empty-state">No documents yet — drag a PDF above to get started.</div>`;
      return;
    }
    container.innerHTML = docs.map(doc => `
      <div class="upload-doc-row" id="upload-row-${doc.doc_id}">
        <div class="upload-doc-info">
          <span class="upload-doc-name">${_esc(doc.filename || doc.doc_id)}</span>
          <span class="upload-doc-status ${doc.status}">${_statusLabel(doc.status, doc.processing_stage)}</span>
        </div>
        <div class="upload-doc-progress" id="progress-bar-${doc.doc_id}">
          <div class="progress-fill" style="width:${doc.progress || 0}%"></div>
        </div>
        <div class="upload-doc-actions">
          ${doc.status === 'failed' ? `<button class="btn-retry" onclick="uploadsPage.retryDoc('${doc.doc_id}')">↺ Retry</button>` : ''}
          ${doc.status === 'ready'  ? `<button class="btn-open"  onclick="selectDoc('${doc.doc_id}', '${_esc(doc.filename)}')">Open →</button>` : ''}
          <button class="btn-icon btn-danger" onclick="uploadsPage.deleteDoc('${doc.doc_id}', '${_esc(doc.filename)}')">🗑</button>
        </div>
      </div>
    `).join('');

    // Start polling for processing docs
    docs.filter(d => d.status === 'processing').forEach(d => _startPolling(d.doc_id));
  }

  function _startPolling(docId) {
    if (_pollingIntervals[docId]) return;
    _pollingIntervals[docId] = setInterval(async () => {
      try {
        const data = await window.api.get(`/status/${docId}`);
        _updateProgress(docId, data);
        if (data.status === 'ready' || data.status === 'failed') {
          clearInterval(_pollingIntervals[docId]);
          delete _pollingIntervals[docId];
          loadDocumentList();
        }
      } catch (_) {
        clearInterval(_pollingIntervals[docId]);
        delete _pollingIntervals[docId];
      }
    }, 3000);
  }

  function _updateProgress(docId, data) {
    const bar = document.querySelector(`#progress-bar-${docId} .progress-fill`);
    if (bar) bar.style.width = `${data.progress || 0}%`;
    const statusEl = document.querySelector(`#upload-row-${docId} .upload-doc-status`);
    if (statusEl) {
      statusEl.textContent = _statusLabel(data.status, data.processing_stage);
      statusEl.className = `upload-doc-status ${data.status}`;
    }
  }

  async function retryDoc(docId) {
    const toastId = window.notifications?.loading('Retrying…');
    try {
      await window.api.post(`/retry/${docId}`);
      window.notifications?.dismiss(toastId);
      window.notifications?.success('Document re-queued');
      _startPolling(docId);
      loadDocumentList();
    } catch (err) {
      window.notifications?.dismiss(toastId);
      window.notifications?.error(err.message || 'Retry failed');
    }
  }

  async function deleteDoc(docId, filename) {
    const ok = await window.modals?.confirm(
      `Delete "${filename}"? This cannot be undone.`, 'Delete', 'Cancel'
    );
    if (!ok) return;
    clearInterval(_pollingIntervals[docId]);
    delete _pollingIntervals[docId];
    const toastId = window.notifications?.loading('Deleting…');
    try {
      await window.api.delete(`/doc/${docId}`);
      window.notifications?.dismiss(toastId);
      window.notifications?.success('Document deleted');
      loadDocumentList();
    } catch (err) {
      window.notifications?.dismiss(toastId);
      window.notifications?.error(err.message || 'Delete failed');
    }
  }

  function _statusLabel(status, stage) {
    if (status === 'ready') return '✓ Ready';
    if (status === 'failed') return '✕ Failed';
    if (status === 'partially_ready') return '~ Partially Ready';
    return `⟳ ${stage || 'Processing'}…`;
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init, loadDocumentList, retryDoc, deleteDoc };
})();

window.uploadsPage = uploadsPage;
