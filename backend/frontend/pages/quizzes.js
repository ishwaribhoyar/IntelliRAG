/**
 * IntelliRAG — Quizzes Page Module
 * 
 * Manages quiz generation, display, submission, and results.
 * Supports quiz + mock_test types with adaptive question rendering.
 * 
 * Usage: quizzesPage.init(userId);
 */

const quizzesPage = (() => {
  let _userId = 'default_user';
  let _docId   = '';
  let _quizType = 'quiz';
  let _questions = [];
  let _answers   = [];
  let _llmVariant = '30b';

  function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    window.sidebar?.setActivePage('quizzes');
    _bindEvents();
  }

  function _bindEvents() {
    const startBtn = document.getElementById('quiz-start-btn');
    if (startBtn) startBtn.addEventListener('click', startQuiz);

    const submitBtn = document.getElementById('quiz-submit-btn');
    if (submitBtn) submitBtn.addEventListener('click', submitQuiz);

    const typeToggle = document.getElementById('quiz-type-select');
    if (typeToggle) typeToggle.addEventListener('change', e => { _quizType = e.target.value; });

    const variantToggle = document.getElementById('quiz-llm-variant');
    if (variantToggle) variantToggle.addEventListener('change', e => { _llmVariant = e.target.value; });

    const docSel = document.getElementById('quiz-doc-select');
    if (docSel) docSel.addEventListener('change', e => { _docId = e.target.value; });
  }

  async function startQuiz() {
    _docId = _docId || document.getElementById('quiz-doc-select')?.value || window.currentDocId || '';
    if (!_docId) { window.notifications?.error('Please select a document first'); return; }

    const btn = document.getElementById('quiz-start-btn');
    const container = document.getElementById('quiz-container');
    window.loaders?.setLoading(btn, true, 'Generating…');
    if (container) window.loaders?.skeleton(container, 5);

    try {
      const data = await window.aiService.startQuiz(_docId, _quizType, _userId, _llmVariant);
      _questions = data.questions || [];
      _answers   = new Array(_questions.length).fill(null);
      if (container) _renderQuestions(container);
      document.getElementById('quiz-submit-btn')?.removeAttribute('disabled');
      window.notifications?.success(`${_questions.length} questions generated!`);
    } catch (err) {
      if (container) window.loaders?.clearSkeleton(container);
      window.notifications?.error(err.message || 'Failed to generate quiz');
    } finally {
      window.loaders?.setLoading(btn, false);
    }
  }

  function _renderQuestions(container) {
    window.loaders?.clearSkeleton(container);
    container.innerHTML = _questions.map((q, i) => {
      const opts = (q.options || []).map((opt, oi) => `
        <label class="quiz-option" for="q${i}-opt${oi}">
          <input type="radio" id="q${i}-opt${oi}" name="q${i}" value="${oi}" onchange="quizzesPage._onAnswer(${i}, '${oi}')">
          <span>${_esc(opt)}</span>
        </label>
      `).join('');
      return `
        <div class="quiz-question" id="q-${i}">
          <p class="quiz-q-text"><strong>Q${i + 1}.</strong> ${_esc(q.question || q.text || '')}</p>
          <div class="quiz-options">${opts}</div>
        </div>
      `;
    }).join('');
  }

  function _onAnswer(questionIndex, optionIndex) {
    _answers[questionIndex] = String(optionIndex);
  }

  async function submitQuiz() {
    if (!_questions.length) { window.notifications?.error('No quiz loaded'); return; }
    const answered = _answers.filter(a => a !== null).length;
    if (answered < _questions.length) {
      const ok = await window.modals?.confirm(`You've answered ${answered}/${_questions.length} questions. Submit anyway?`);
      if (!ok) return;
    }

    const btn = document.getElementById('quiz-submit-btn');
    window.loaders?.setLoading(btn, true, 'Grading…');

    try {
      const data = await window.aiService.submitQuiz(
        _docId, _userId, _questions,
        _answers.map(a => a ?? ''),
        _quizType,
      );
      _renderResults(data);
      window.notifications?.success(`Score: ${data.score}/${data.total} (${Math.round(data.accuracy * 100)}%)`);
    } catch (err) {
      window.notifications?.error(err.message || 'Failed to grade quiz');
    } finally {
      window.loaders?.setLoading(btn, false);
    }
  }

  function _renderResults(data) {
    const resultsEl = document.getElementById('quiz-results');
    if (!resultsEl) return;
    const pct = Math.round((data.accuracy || 0) * 100);
    const color = pct >= 75 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
    resultsEl.innerHTML = `
      <div class="quiz-score-card" style="border-color:${color}">
        <div class="score-big" style="color:${color}">${pct}%</div>
        <div class="score-sub">${data.score}/${data.total} correct</div>
        ${data.xp ? `<div class="score-xp">+${data.xp?.gained || 0} XP earned 🎉</div>` : ''}
      </div>
      ${_renderDetails(data.details || [])}
    `;
    resultsEl.scrollIntoView({ behavior: 'smooth' });
  }

  function _renderDetails(details) {
    return details.map((d, i) => `
      <div class="quiz-detail ${d.is_correct ? 'correct' : 'incorrect'}">
        <p><strong>Q${i + 1}:</strong> ${_esc(d.question || '')}</p>
        <p>Your answer: <em>${_esc(d.user_answer || 'No answer')}</em>
        ${d.is_correct ? ' ✓' : ` ✗ — Correct: <em>${_esc(d.correct_answer || '')}</em>`}</p>
        ${d.explanation ? `<p class="quiz-explanation">${_esc(d.explanation)}</p>` : ''}
      </div>
    `).join('');
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init, startQuiz, submitQuiz, _onAnswer };
})();

window.quizzesPage = quizzesPage;
