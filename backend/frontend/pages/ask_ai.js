/**
 * IntelliRAG — Ask AI Page Module
 * 
 * Manages the Ask AI view: query input, answer display,
 * source chunk citations, confidence badge, and doc scope toggle.
 * 
 * Usage: askPage.init(userId);
 */

const askPage = (() => {
  let _userId = 'default_user';
  let _scopeDocId = null;
  let _llmVariant  = '30b';
  let _history = [];

  function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    window.sidebar?.setActivePage('ask');
    _bindEvents();
  }

  function _bindEvents() {
    const form = document.getElementById('ask-form');
    if (form) form.addEventListener('submit', _onSubmit);

    const variantToggle = document.getElementById('ask-llm-variant');
    if (variantToggle) variantToggle.addEventListener('change', e => { _llmVariant = e.target.value; });

    const clearBtn = document.getElementById('ask-clear-history');
    if (clearBtn) clearBtn.addEventListener('click', clearHistory);

    const docSel = document.getElementById('ask-doc-scope');
    if (docSel) docSel.addEventListener('change', e => { _scopeDocId = e.target.value || null; });
  }

  async function _onSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('ask-input');
    const query = (input?.value || '').trim();
    if (!query) return;

    const btn = document.getElementById('ask-submit-btn');
    window.loaders?.setLoading(btn, true, 'Thinking…');
    _appendMessage('user', query);
    if (input) input.value = '';

    try {
      const data = await window.aiService.ask(query, _userId, _scopeDocId, _llmVariant);
      _history.push({ role: 'user', content: query });
      _appendMessage('ai', data.answer || 'No answer generated.', data);
      _history.push({ role: 'assistant', content: data.answer });
    } catch (err) {
      _appendMessage('error', err.message || 'Something went wrong');
      window.notifications?.error(err.message || 'Ask AI failed');
    } finally {
      window.loaders?.setLoading(btn, false);
    }
  }

  function _appendMessage(role, content, data = null) {
    const feed = document.getElementById('ask-feed') || document.getElementById('ask-results');
    if (!feed) return;

    const div = document.createElement('div');
    div.className = `ask-message ask-message--${role}`;

    if (role === 'ai' && data) {
      const conf = data.confidence?.level || data.confidence_label || 'medium';
      const confColor = { high: '#10b981', medium: '#f59e0b', low: '#ef4444' }[conf] || '#94a3b8';
      const cached = data.cached ? '<span class="cache-badge">⚡ cached</span>' : '';
      const sources = _renderSources(data.source_chunks || []);
      div.innerHTML = `
        <div class="ai-answer-header">
          <span class="ai-badge">🤖 IntelliRAG AI</span>
          <span class="confidence-badge" style="color:${confColor}">● ${conf} confidence</span>
          ${cached}
        </div>
        <div class="ai-answer-body">${_renderMarkdown(content)}</div>
        ${sources}
      `;
    } else if (role === 'user') {
      div.innerHTML = `<div class="user-bubble">${_esc(content)}</div>`;
    } else {
      div.innerHTML = `<div class="error-bubble">⚠ ${_esc(content)}</div>`;
    }

    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
  }

  function _renderSources(chunks) {
    if (!chunks.length) return '';
    const items = chunks.slice(0, 3).map(c => `
      <li class="source-item">
        <span class="source-page">p.${c.page || '?'}</span>
        <span class="source-text">${_esc((c.text || '').slice(0, 100))}…</span>
      </li>
    `).join('');
    return `<details class="sources-toggle"><summary>Sources (${chunks.length})</summary><ul>${items}</ul></details>`;
  }

  function _renderMarkdown(text) {
    // Basic markdown: bold, bullet lists, headings
    return String(text || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
      .replace(/\n{2,}/g, '</p><p>')
      .replace(/\n/g, '<br>');
  }

  function clearHistory() {
    _history = [];
    const feed = document.getElementById('ask-feed') || document.getElementById('ask-results');
    if (feed) feed.innerHTML = '';
    window.notifications?.info('Conversation cleared');
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init, clearHistory };
})();

window.askPage = askPage;
