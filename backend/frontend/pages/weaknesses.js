/**
 * IntelliRAG — Weaknesses Page Module
 * 
 * Displays weak topics with AI-generated advice, study plan,
 * and subject-level performance breakdown.
 * 
 * Usage: weaknessesPage.init(userId);
 */

const weaknessesPage = (() => {
  let _userId = 'default_user';

  function init(userId) {
    _userId = userId || window.authService?.getCurrentUserId() || 'default_user';
    window.sidebar?.setActivePage('weaknesses');
    loadWeaknesses();
  }

  async function loadWeaknesses() {
    const container = document.getElementById('weakness-container') || document.getElementById('weakness-content');
    if (container) window.loaders?.skeleton(container, 4);

    try {
      const data = await window.api.get(`/weakness/${_userId}`);
      window.loaders?.clearSkeleton(container);
      _render(data, container);
    } catch (err) {
      if (container) window.loaders?.clearSkeleton(container);
      window.notifications?.error('Failed to load weakness analysis');
    }
  }

  function _render(data, container) {
    if (!container) return;
    const weak    = data.weak_topics || [];
    const subj    = data.subject_summary || [];
    const plan    = data.study_plan || {};

    container.innerHTML = `
      ${_renderSubjectSummary(subj)}
      ${_renderWeakTopics(weak)}
      ${_renderStudyPlan(plan)}
    `;
  }

  function _renderSubjectSummary(subjects) {
    if (!subjects.length) return '';
    return `
      <section class="weakness-section">
        <h3 class="section-title">📊 Subject Overview</h3>
        <div class="subject-grid">
          ${subjects.map(s => `
            <div class="subject-stat-card">
              <h4>${_esc(s.subject)}</h4>
              <div class="stat-row">
                <span class="stat weak">Weak: ${s.weak || 0}</span>
                <span class="stat moderate">Moderate: ${s.moderate || 0}</span>
                <span class="stat strong">Strong: ${s.strong || 0}</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" style="width:${_pct(s.strong, s.total)}%;background:#10b981"></div>
              </div>
            </div>
          `).join('')}
        </div>
      </section>
    `;
  }

  function _renderWeakTopics(topics) {
    if (!topics.length) return `
      <section class="weakness-section">
        <div class="empty-state">🎉 No weak topics found! Keep practicing.</div>
      </section>
    `;
    return `
      <section class="weakness-section">
        <h3 class="section-title">⚠️ Topics to Improve</h3>
        <div class="weakness-grid">
          ${topics.map(t => `
            <div class="weakness-card">
              <div class="weakness-header">
                <span class="weakness-topic">${_esc(t.topic)}</span>
                <span class="weakness-accuracy" style="color:${_color(t.accuracy)}">
                  ${Math.round((t.accuracy || 0) * 100)}%
                </span>
              </div>
              <div class="accuracy-bar">
                <div class="accuracy-fill" style="width:${Math.round((t.accuracy || 0) * 100)}%;background:${_color(t.accuracy)}"></div>
              </div>
              <p class="attempts-info">${t.correct || 0} correct of ${t.total || 0} attempts</p>
              ${t.advice ? `<p class="weakness-advice">💡 ${_esc(t.advice)}</p>` : ''}
            </div>
          `).join('')}
        </div>
      </section>
    `;
  }

  function _renderStudyPlan(plan) {
    const steps = plan.steps || plan.suggestions || [];
    if (!steps.length) return '';
    return `
      <section class="weakness-section">
        <h3 class="section-title">📅 Recommended Study Plan</h3>
        <ol class="study-plan-list">
          ${steps.map(s => `<li>${_esc(typeof s === 'string' ? s : s.text || JSON.stringify(s))}</li>`).join('')}
        </ol>
      </section>
    `;
  }

  function _pct(val, total) {
    return total ? Math.round((val / total) * 100) : 0;
  }

  function _color(accuracy) {
    const pct = (accuracy || 0) * 100;
    return pct >= 75 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
  }

  function _esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  return { init, loadWeaknesses };
})();

window.weaknessesPage = weaknessesPage;
