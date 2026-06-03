/**
 * IntelliRAG — Flashcards Page Module
 * 
 * Manages content generation: flashcards, summary, slides, fun_facts,
 * rapid_fire, true_false, fill_blanks. Includes card-flip animation.
 * 
 * Usage: flashcardsPage.init(userId);
 */

const flashcardsPage = (() => {
  let _userId = 'default_user';
  let _docId = '';
  let _contentType = 'flashcards';
  let _llmVariant  = '30b';
  let _cards = [];
  let _currentCard = 0;

  function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    window.sidebar?.setActivePage('flashcards');
    _bindEvents();
  }

  function _bindEvents() {
    const genBtn = document.getElementById('flashcards-generate-btn');
    if (genBtn) genBtn.addEventListener('click', generate);

    const refreshBtn = document.getElementById('flashcards-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => generate(true));

    const typeSelect = document.getElementById('content-type-select');
    if (typeSelect) typeSelect.addEventListener('change', e => { _contentType = e.target.value; });

    const docSel = document.getElementById('flashcards-doc-select');
    if (docSel) docSel.addEventListener('change', e => { _docId = e.target.value; });

    const prevBtn = document.getElementById('flashcard-prev');
    if (prevBtn) prevBtn.addEventListener('click', prevCard);

    const nextBtn = document.getElementById('flashcard-next');
    if (nextBtn) nextBtn.addEventListener('click', nextCard);
  }

  async function generate(refresh = false) {
    _docId = _docId || document.getElementById('flashcards-doc-select')?.value || window.currentDocId || '';
    if (!_docId) { window.notifications?.error('Please select a document first'); return; }

    const btn = document.getElementById('flashcards-generate-btn');
    const container = document.getElementById('flashcards-container');
    window.loaders?.setLoading(btn, true, 'Generating…');
    if (container) window.loaders?.skeleton(container, 4);

    try {
      const data = await window.aiService.generate(_docId, _contentType, _userId, '', refresh, _llmVariant);
      _processResult(data, container);
      window.notifications?.success('Content generated!');
    } catch (err) {
      if (container) window.loaders?.clearSkeleton(container);
      window.notifications?.error(err.message || 'Generation failed');
    } finally {
      window.loaders?.setLoading(btn, false);
    }
  }

  function _processResult(data, container) {
    if (!container) return;
    window.loaders?.clearSkeleton(container);

    if (_contentType === 'flashcards') {
      _cards = data.flashcards || data.items || [];
      _currentCard = 0;
      _renderFlashcardDeck(container);
    } else if (_contentType === 'summary') {
      container.innerHTML = `<div class="prose-output">${_mdToHtml(data.summary || data.answer || '')}</div>`;
    } else if (_contentType === 'slides') {
      _renderSlides(container, data.slides || []);
    } else if (_contentType === 'fun_facts') {
      _renderList(container, data.facts || data.items || [], 'fun-fact');
    } else {
      // rapid_fire, true_false, fill_blanks — treat as quiz-like
      container.innerHTML = `<pre class="raw-output">${JSON.stringify(data, null, 2)}</pre>`;
    }
  }

  function _renderFlashcardDeck(container) {
    if (!_cards.length) {
      container.innerHTML = '<p class="empty-state">No flashcards generated</p>';
      return;
    }
    container.innerHTML = `
      <div class="flashcard-deck">
        <div class="flashcard" id="main-flashcard" onclick="flashcardsPage.flipCard()">
          <div class="flashcard-inner" id="flashcard-inner">
            <div class="flashcard-front">
              <p>${_esc(_cards[0]?.front || _cards[0]?.question || '')}</p>
            </div>
            <div class="flashcard-back">
              <p>${_esc(_cards[0]?.back || _cards[0]?.answer || '')}</p>
            </div>
          </div>
        </div>
        <div class="flashcard-controls">
          <button id="flashcard-prev" onclick="flashcardsPage.prevCard()" class="btn-secondary">← Prev</button>
          <span id="flashcard-counter">1 / ${_cards.length}</span>
          <button id="flashcard-next" onclick="flashcardsPage.nextCard()" class="btn-secondary">Next →</button>
        </div>
      </div>
    `;
  }

  function flipCard() {
    document.getElementById('flashcard-inner')?.classList.toggle('flipped');
  }

  function prevCard() {
    if (_currentCard > 0) { _currentCard--; _updateCard(); }
  }

  function nextCard() {
    if (_currentCard < _cards.length - 1) { _currentCard++; _updateCard(); }
  }

  function _updateCard() {
    const card = _cards[_currentCard];
    const inner = document.getElementById('flashcard-inner');
    if (!inner) return;
    inner.classList.remove('flipped');
    const front = inner.querySelector('.flashcard-front p');
    const back  = inner.querySelector('.flashcard-back p');
    if (front) front.textContent = card?.front || card?.question || '';
    if (back)  back.textContent  = card?.back  || card?.answer   || '';
    const counter = document.getElementById('flashcard-counter');
    if (counter) counter.textContent = `${_currentCard + 1} / ${_cards.length}`;
  }

  function _renderSlides(container, slides) {
    container.innerHTML = slides.map((s, i) => `
      <div class="slide-card">
        <div class="slide-num">Slide ${i + 1}</div>
        <h3>${_esc(s.title || '')}</h3>
        <ul>${(s.points || []).map(p => `<li>${_esc(p)}</li>`).join('')}</ul>
      </div>
    `).join('');
  }

  function _renderList(container, items, cls) {
    container.innerHTML = `<ul class="${cls}-list">${items.map(it => `<li class="${cls}-item">${_esc(typeof it === 'string' ? it : it.text || JSON.stringify(it))}</li>`).join('')}</ul>`;
  }

  function _mdToHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init, generate, flipCard, prevCard, nextCard };
})();

window.flashcardsPage = flashcardsPage;
