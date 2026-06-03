// Keep consistent with main app auth state in `app.js` which stores `intellirag_uid`.
const userId =
  localStorage.getItem('intellirag_uid') ||
  localStorage.getItem('intellirag_user_id') ||
  'default_user';
let searchMode = 'hybrid';
let suggestTimer = null;
let activeSuggest = -1;
let currentQuery = '';

let activeDocId = '';
let activeNodeId = '';
let activeChunkId = '';

const el = (id) => document.getElementById(id);
const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

async function api(endpoint, body) {
  const res = await fetch('/api/' + endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

async function get(endpoint) {
  const res = await fetch('/api/' + endpoint);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

function highlight(text, q) {
  const raw = esc(text || '');
  if (!q) return raw;
  const t = q.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!t) return raw;
  return raw.replace(new RegExp(`(${t})`, 'ig'), '<mark class="sr-highlight">$1</mark>');
}

function highlightQueryTerms(text, q) {
  const raw = esc(text || '');
  if (!q) return raw;
  const terms = String(q)
    .toLowerCase()
    .split(/\s+/)
    .map(t => t.trim())
    .filter(t => t.length > 2);
  if (!terms.length) return raw;

  let out = raw;
  terms.forEach(term => {
    const safe = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(${safe})`, 'ig');
    out = out.replace(re, '<mark class="sr-highlight">$1</mark>');
  });
  return out;
}

async function doSearch() {
  const q = (el('searchInput').value || '').trim();
  if (!q) return;
  currentQuery = q;
  el('searchResults').innerHTML = '<div class="skeleton-block"></div><div class="skeleton-block"></div>';
  const t0 = performance.now();
  try {
    const payload = { user_id: userId, query: q, mode: searchMode, limit: 30 };
    console.log('[Search] POST /api/search/user payload:', payload);
    const d = await api('search/user', payload);
    const elapsed = Math.round(performance.now() - t0);
    const list = d.results || [];
    console.log('[Search] response:', {
      results: list.length,
      mode: d.mode,
      did_you_mean: d.did_you_mean || null,
      elapsed_ms: elapsed,
    });
    let html = `<div class="sr-meta"><span class="sr-chip">${list.length} results</span><span class="sr-chip">${elapsed}ms</span></div>`;
    html += '<div class="sr-results-list">';
    for (const r of list) {
      const docId = r.doc_id || '';
      const nodeId = r.node_id || '';
      const chunkId = r.chunk_id || '';
      html += `<div
        class="sr-google-card"
        role="button"
        tabindex="0"
        data-doc-id="${esc(docId)}"
        data-node-id="${esc(nodeId)}"
        data-chunk-id="${esc(chunkId)}"
        data-page="${esc(r.page || 1)}"
        data-snippet="${esc(r.snippet || r.text || '')}"
        onclick="onResultCardClick(this)"
      >
        <div class="sr-g-title">${esc(r.title || r.section || r.doc_id)}</div>
        <div class="sr-g-url">📄 ${esc(r.filename || r.doc_id)} · Page ${r.page || 1}${r.section_path ? ' · ' + esc(r.section_path) : ''}</div>
        <div class="sr-g-snippet">${highlight(r.snippet || r.text || '', q)}</div>
        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn btn-ghost btn-sm" type="button" onclick="event.stopPropagation(); const card = this.closest('.sr-google-card'); openPdfViewer(card.dataset.docId, card.dataset.page, currentQuery || '', card.dataset.snippet);">Open in PDF</button>
        </div>
      </div>`;
    }
    html += '</div>';
    el('searchResults').innerHTML = html;
  } catch (e) {
    console.error('[Search] doSearch error:', e);
    el('searchResults').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
  }
}

async function loadNodeChunksAndScroll(docId, nodeId, chunkId) {
  activeDocId = docId || '';
  activeNodeId = nodeId || '';
  activeChunkId = chunkId || '';

  const readerTitle = el('readerTitle');
  const readerMeta = el('readerMeta');
  const readerChunks = el('readerChunks');

  if (readerTitle) readerTitle.textContent = 'Loading section...';
  if (readerMeta) readerMeta.textContent = `Doc: ${docId}`;
  if (readerChunks) readerChunks.innerHTML = 'Loading chunks...';

  try {
    const resp = await fetch(`/api/node_chunks/${encodeURIComponent(docId)}/${encodeURIComponent(nodeId)}?user_id=${encodeURIComponent(userId)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Failed to load node chunks');

    const chunks = data.chunks || [];
    if (!readerTitle) return;

    readerTitle.textContent = data.node_title || data.node_id || 'Section';
    if (readerMeta) readerMeta.textContent = `Doc: ${docId} · Chunks: ${chunks.length}`;

    readerChunks.innerHTML = '';
    chunks.forEach(c => {
      const cid = c.chunk_id || '';
      const pid = c.page || 1;
      const wrapperId = `chunk-${cid}`;
      const div = document.createElement('div');
      div.className = 'sr-chunk';
      div.id = wrapperId;
      div.innerHTML = `<div class="sr-chunk-text">${highlightQueryTerms(c.text || '', currentQuery)}</div><div style="font-size:11px;color:var(--text-3);margin-top:6px">Page ${pid}</div>`;
      readerChunks.appendChild(div);
    });

    const target = document.getElementById(`chunk-${chunkId}`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      const first = readerChunks.querySelector('.sr-chunk');
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch (e) {
    if (readerChunks) readerChunks.innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    if (readerTitle) readerTitle.textContent = 'Failed to load';
  }
}

function onResultCardClick(cardEl) {
  const docId = cardEl?.dataset?.docId || '';
  const nodeId = cardEl?.dataset?.nodeId || '';
  const chunkId = cardEl?.dataset?.chunkId || '';
  const page = parseInt(cardEl?.dataset?.page || '1', 10) || 1;
  const snippet = cardEl?.dataset?.snippet || '';
  if (!docId || !nodeId) return;

  // Open PDF at the page containing the match (fragment navigation).
  // Even if highlighting fails, the page jump should still work.
  try {
    openPdfViewer(docId, page, currentQuery || '', snippet);
  } catch (e) {}

  loadNodeChunksAndScroll(docId, nodeId, chunkId);
}

function openPdfViewer(docId, page = 1, query = '', snippet = '') {
  const q = new URLSearchParams();
  q.set('doc_id', decodeURIComponent(String(docId || '')));
  q.set('page', String(parseInt(page, 10) || 1));
  const cleanQ = decodeURIComponent(String(query || ''));
  if (cleanQ) q.set('query', cleanQ);
  const cleanSnippet = decodeURIComponent(String(snippet || ''));
  if (cleanSnippet) q.set('snippet', cleanSnippet);
  window.open(`/pdf-viewer.html?${q.toString()}`, '_blank', 'noopener');
}

async function fetchSuggestions() {
  const q = (el('searchInput').value || '').trim();
  const box = el('searchSuggestBox');
  if (!q || q.length < 2) {
    box.style.display = 'none';
    box.innerHTML = '';
    activeSuggest = -1;
    return;
  }
  const endpoint = `search/suggest/user/${encodeURIComponent(userId)}?q=${encodeURIComponent(q)}&limit=5`;
  console.log('[Search] GET /api/' + endpoint);
  let d;
  try {
    d = await get(endpoint);
  } catch (e) {
    console.error('[Search] fetchSuggestions error:', e);
    box.style.display = 'none';
    box.innerHTML = '';
    activeSuggest = -1;
    return;
  }
  const items = d.suggestions || [];
  console.log('[Search] suggestions response:', {
    query: q,
    suggestions: items,
  });
  if (!items.length) {
    box.style.display = 'none';
    box.innerHTML = '';
    activeSuggest = -1;
    return;
  }
  box.innerHTML = items.map((s, i) => `<button class="sr-suggest-item" type="button" data-idx="${i}" data-suggest="${esc(s)}">${highlight(s, q)}</button>`).join('');
  box.style.display = 'block';
  activeSuggest = -1;
}

document.addEventListener('DOMContentLoaded', () => {
  const input = el('searchInput');
  const btn = el('searchBtn');
  const box = el('searchSuggestBox');

  document.querySelectorAll('.mode-chip').forEach((m) => {
    m.addEventListener('click', () => {
      document.querySelectorAll('.mode-chip').forEach((x) => x.classList.remove('active'));
      m.classList.add('active');
      searchMode = m.dataset.mode || 'hybrid';
    });
  });

  input.addEventListener('input', () => {
    if (suggestTimer) clearTimeout(suggestTimer);
    suggestTimer = setTimeout(fetchSuggestions, 250);
  });
  input.addEventListener('keydown', (e) => {
    const items = Array.from(box.querySelectorAll('.sr-suggest-item'));
    if (e.key === 'Enter') {
      e.preventDefault();
      if (activeSuggest >= 0 && activeSuggest < items.length) {
        input.value = items[activeSuggest].dataset.suggest || '';
      }
      doSearch();
      box.style.display = 'none';
      return;
    }
    if (!items.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeSuggest = (activeSuggest + 1) % items.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeSuggest = (activeSuggest - 1 + items.length) % items.length;
    }
    items.forEach((it, idx) => it.classList.toggle('active', idx === activeSuggest));
  });

  box.addEventListener('click', (e) => {
    const btn = e.target.closest('.sr-suggest-item');
    if (!btn) return;
    console.log('[Search] Click suggestion:', btn.dataset.suggest || '');
    input.value = btn.dataset.suggest || '';
    box.style.display = 'none';
    doSearch();
  });

  btn.addEventListener('click', doSearch);
});
