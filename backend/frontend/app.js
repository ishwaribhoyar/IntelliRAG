// ============================================================
// IntelliRAG — Frontend Logic
// ============================================================

// ── State ────────────────────────────────────────────────────
const STATE = {
  userId:      localStorage.getItem('intellirag_uid')  || null,
  username:    localStorage.getItem('intellirag_name') || null,
  email:       localStorage.getItem('intellirag_email')|| null,
  docId:       localStorage.getItem('intellirag_docid')|| null,
  docFilename: localStorage.getItem('intellirag_docfn')|| null,
  xp: 0, level: 1, streak: 0,
  currentQuiz: null,
  currentQuizMeta: null,
  quizByKey: { quiz: [], mock: [] },
  quizAnswers: { quiz: {}, mock: {} },
  _flashcards: [], _fcIdx: 0,
  /** Sarvam chat: "105b" | "30b" — persisted under `intellirag` */
  llmVariant:  localStorage.getItem('intellirag') === '105b' ? '105b' : '30b',
  refreshBundle: {
    quiz:        { doc_id: null, source_chunk_ids: [], previous_output: null },
    mock_test:   { doc_id: null, source_chunk_ids: [], previous_output: null },
    flashcards:  { doc_id: null, source_chunk_ids: [], previous_output: null },
    summary:     { doc_id: null, source_chunk_ids: [], previous_output: null },
  },
  lastAskTopic: '',
  lastAskQuery: '',
  currentView: 'dashboard',
};

function getLlmVariant() {
  return STATE.llmVariant === '30b' ? '30b' : '105b';
}

function setLlmVariant(v) {
  STATE.llmVariant = (v === '30b' ? '30b' : '105b');
  localStorage.setItem('intellirag', STATE.llmVariant);
  syncLlmModelToggle();
}

function syncLlmModelToggle() {
  const cur = getLlmVariant();
  document.querySelectorAll('.llm-model-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.variant === cur);
  });
}

function captureFeatureContext(feature, apiResponse) {
  const ids = (apiResponse.source_chunks || []).map((s) => s.chunk_id).filter(Boolean);
  const b = STATE.refreshBundle[feature] || {};
  b.doc_id = STATE.docId;
  b.source_chunk_ids = ids;
  STATE.refreshBundle[feature] = b;
}

function getRefreshPayload(feature) {
  const b = STATE.refreshBundle[feature] || {};
  if (!STATE.docId || b.doc_id !== STATE.docId) {
    return { previous_output: null, source_chunk_ids: null };
  }
  return {
    previous_output: b.previous_output || null,
    source_chunk_ids: b.source_chunk_ids?.length ? [...b.source_chunk_ids] : null,
  };
}

function setRefreshLoading(feature, loading) {
  document.querySelectorAll(`[data-refresh-feature="${feature}"]`).forEach((btn) => {
    btn.disabled = !!loading;
    btn.textContent = loading ? 'Regenerating…' : 'Refresh 🔄';
  });
}

async function refreshFeature(feature) {
  if (!STATE.docId) return;
  try {
    setRefreshLoading(feature, true);
    if (feature === 'quiz') {
      if (!el('quizContent')) return;
      await loadQuizType('quiz', 'quizContent', { refresh: true });
    } else if (feature === 'mock_test') {
      if (!el('mocktestContent')) return;
      await loadQuizType('mock_test', 'mocktestContent', { refresh: true });
    } else if (feature === 'flashcards') {
      if (!el('flashcardsContent')) return;
      await initFlashcards({ refresh: true });
    } else if (feature === 'summary') {
      if (!el('summaryContent')) return;
      await initSummary({ refresh: true });
    }
  } catch (e) {
    console.error('[refreshFeature]', feature, e);
  } finally {
    setRefreshLoading(feature, false);
  }
}

// Helper to persist doc selection
function _saveDocState() {
  if (STATE.docId) {
    localStorage.setItem('intellirag_docid', STATE.docId);
    localStorage.setItem('intellirag_docfn', STATE.docFilename || '');
  } else {
    localStorage.removeItem('intellirag_docid');
    localStorage.removeItem('intellirag_docfn');
  }
}

// ── Boot ─────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  if (STATE.userId) {
    updateUserUI();
    // Restore topbar if doc was previously selected
    if (STATE.docId) {
      const fn = el('topbarFilename');
      const sb = el('topbarStatus');
      if (fn) fn.textContent = STATE.docFilename || STATE.docId || 'Document';
      if (sb) sb.textContent = 'READY';
    }
    smartRoute();
    fetchScore();
    syncLlmModelToggle();
  } else {
    showLogin();
  }
});

// ── AUTH VIEW TOGGLES ─────────────────────────────────────────
function showLogin()    { s('authView','flex'); s('loginCard','block'); s('registerCard','none'); clearAuthErrors(); }
function showRegister() { s('authView','flex'); s('loginCard','none'); s('registerCard','block'); clearAuthErrors(); }
function clearAuthErrors() {
  ['loginEmailErr','loginPwErr','loginGlobalErr','regNameErr','regEmailErr','regPwErr','regConfirmErr','regGlobalErr']
    .forEach(id => { const e=el(id); if(e) e.textContent=''; });
}

// ── SHOW UPLOAD / APP ─────────────────────────────────────────
function showUpload() {
  s('authView','none'); s('uploadView','flex'); s('appShell','none');
  window.scrollTo(0, 0);
}
function showApp() {
  s('authView','none'); s('uploadView','none'); s('appShell','flex');
  window.scrollTo(0, 0);
  syncLlmModelToggle();
  go('library');
}
function doLogout() {
  ['intellirag_uid','intellirag_name','intellirag_email','intellirag_docid','intellirag_docfn'].forEach(k => localStorage.removeItem(k));
  Object.assign(STATE, {userId:null, username:null, email:null, docId:null, docFilename:null});
  showLogin();
}
function newDoc() { resetRefreshBundle(); STATE.docId=null; STATE.docFilename=null; _saveDocState(); go('library'); }

// Smart routing: logged-in users always go to Library (which has inline upload)
async function smartRoute() {
  if (STATE.userId) {
    showApp();  // Library has its own upload zone
  } else {
    showLogin();
  }
}

// ── REGISTER ──────────────────────────────────────────────────
async function doRegister() {
  clearAuthErrors();
  const name  = val('regName').trim();
  const email = val('regEmail').trim();
  const pw    = val('regPassword');
  const cpw   = val('regConfirm');

  let ok = true;
  if (!name || name.length < 2) { setErr('regNameErr','Enter your full name'); ok=false; }
  if (!isEmail(email)) { setErr('regEmailErr','Enter a valid email address'); ok=false; }
  if (pw.length < 8)   { setErr('regPwErr','Password must be at least 8 characters'); ok=false; }
  if (pw !== cpw)      { setErr('regConfirmErr','Passwords do not match'); ok=false; }
  if (!ok) return;

  setBtnLoading('registerBtn', true);
  try {
    const res = await api('register', { username: email, name, email, password: pw });
    STATE.userId   = res.user_id;
    STATE.username = res.username || name;
    STATE.email    = email;
    persist();
    updateUserUI();
    smartRoute();
  } catch(e) { setErr('regGlobalErr', e.message); }
  finally { setBtnLoading('registerBtn', false); }
}

// ── LOGIN ─────────────────────────────────────────────────────
async function doLogin() {
  clearAuthErrors();
  const email = val('loginEmail').trim();
  const pw    = val('loginPassword');

  let ok = true;
  if (!isEmail(email)) { setErr('loginEmailErr','Enter a valid email address'); ok=false; }
  if (!pw)             { setErr('loginPwErr','Password is required'); ok=false; }
  if (!ok) return;

  setBtnLoading('loginBtn', true);
  try {
    const res = await api('login', { username: email, password: pw });
    STATE.userId   = res.user_id;
    STATE.username = res.username || email;
    STATE.email    = email;
    STATE.xp=res.xp; STATE.level=res.level; STATE.streak=res.streak;
    persist();
    updateUserUI();
    // Hide login immediately, then route
    s('authView','none');
    window.scrollTo(0, 0);
    await smartRoute();
  } catch(e) { setErr('loginGlobalErr', e.message); }
  finally { setBtnLoading('loginBtn', false); }
}

// ── PASSWORD STRENGTH ─────────────────────────────────────────
function checkPwStrength(pw) {
  const bar   = el('pwStrength');
  const fill  = el('pwFill');
  const label = el('pwLabel');
  if (!bar) return;
  if (!pw) { bar.style.display='none'; return; }
  bar.style.display='flex';
  let score = 0;
  if (pw.length >= 8)         score++;
  if (/[A-Z]/.test(pw))       score++;
  if (/[0-9]/.test(pw))       score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const map = [
    { w:'20%', c:'#DC2626', t:'Weak' },
    { w:'45%', c:'#F59E0B', t:'Fair' },
    { w:'70%', c:'#3B82F6', t:'Good' },
    { w:'100%',c:'#16A34A', t:'Strong' },
  ];
  const s = map[score > 0 ? Math.min(score-1, 3) : 0];
  fill.style.width      = s.w;
  fill.style.background = s.c;
  label.style.color     = s.c;
  label.textContent     = s.t;
}

// ── TOGGLE PASSWORD VISIBILITY ────────────────────────────────
function togglePw(inputId, btn) {
  const inp = el(inputId);
  const show = inp.type === 'password';
  inp.type   = show ? 'text' : 'password';
  btn.textContent = show ? 'Hide' : 'Show';
}

// ── USER UI ───────────────────────────────────────────────────
function updateUserUI() {
  const n = STATE.username || STATE.email || 'User';
  const initial = n.charAt(0).toUpperCase();
  setText('sidebarName', n);
  const tierStr = STATE.tier ? ` · ${STATE.tier.charAt(0).toUpperCase() + STATE.tier.slice(1)}` : '';
  setText('sidebarMeta', `${STATE.xp} XP · Lv ${STATE.level}${tierStr}`);
  setText('sidebarAvatar', initial);
  setText('topbarAvatar', initial);
  setText('xpTopbar', `${STATE.xp} XP`);
  setText('lvTopbar', STATE.level);

  // Sync sidebar upgrade card visibility
  const upCard = el('sidebarUpgradeCard');
  if (upCard) {
    upCard.style.display = STATE.tier === 'free' || !STATE.tier ? 'flex' : 'none';
  }
}

function updateStats(xp, level, streak) {
  STATE.xp=xp; STATE.level=level; STATE.streak=streak;
  updateUserUI();
}

async function fetchScore() {
  if (!STATE.userId) return;
  try {
    const d = await get(`score?user_id=${STATE.userId}`);
    updateStats(d.xp, d.level, d.streak);
  } catch{}
  try {
    const prof = await get(`users/profile?user_id=${STATE.userId}`);
    STATE.tier = prof.tier;
    updateUserUI();
  } catch{}
}

// ── UPLOAD ───────────────────────────────────────────────────
const fileInput = document.getElementById('fileInput');
const dropZone  = document.getElementById('uploadDropZone');

if (dropZone) {
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.style.borderColor='var(--primary)'; });
  dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor=''; });
  dropZone.addEventListener('drop', e => {
    e.preventDefault(); dropZone.style.borderColor='';
    const fs = Array.from(e.dataTransfer?.files || []);
    if (fs.length === 1) uploadFile(fs[0]);
    else if (fs.length > 1) uploadFilesMulti(fs);
  });
}
if (fileInput) {
  fileInput.addEventListener('change', e => {
    const fs = Array.from(e.target.files || []);
    if (fs.length === 1) uploadFile(fs[0]);
    else if (fs.length > 1) uploadFilesMulti(fs);
  });
}

async function uploadFilesMulti(files) {
  if (!files || !files.length) return;

  // Show feedback in BOTH places:
  // - Upload view (uploadFeedback/progressSection)
  // - Library view (libUploadFeedback/libProgressSection), since multi-upload is now possible from Library.
  setUploadFeedback(`Uploading ${files.length} document(s)…`);
  setProgress(20, 'Uploading…');
  const libFb = el('libUploadFeedback');
  const libProg = el('libProgressSection');
  const libFill = el('libProgressFill');
  const libLbl = el('libProgressLabel');
  if (libFb) { libFb.textContent = `Uploading ${files.length} document(s)…`; libFb.className = 'lib-upload-fb'; }
  if (libProg) libProg.style.display = 'block';
  if (libFill) libFill.style.width = '20%';
  if (libLbl) libLbl.textContent = 'Uploading…';

  const fd = new FormData();
  // FastAPI endpoint accepts `files[]` (alias) for list[UploadFile].
  for (const f of files) fd.append('files[]', f);
  fd.append('user_id', STATE.userId || 'guest');

  try {
    const res = await fetch('/api/upload/multi', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    const accepted = data.accepted_files || data.accepted || [];
    const rejected = data.rejected_files || data.rejected || [];

    // Update the active doc to the first accepted file to keep existing UX flow working.
    if (accepted.length) {
      const first = accepted[0];
      if (STATE.docId !== first.doc_id) resetRefreshBundle();
      STATE.docId = first.doc_id;
      STATE.docFilename = first.filename || first.doc_id;
      _saveDocState();
      const fn = el('topbarFilename');
      if (fn) fn.textContent = STATE.docFilename;
      if (accepted.length > 1) {
        const msg = `Queued ${accepted.length} docs (${rejected.length} rejected). Processing first…`;
        setUploadFeedback(msg);
        if (libFb) { libFb.textContent = msg; libFb.className = 'lib-upload-fb'; }
      } else if (rejected.length) {
        const msg = `Processing (some rejected): ${rejected.length} rejected.`;
        setUploadFeedback(msg);
        if (libFb) { libFb.textContent = msg; libFb.className = 'lib-upload-fb'; }
      }
    } else {
      throw new Error(rejected?.[0]?.error || 'No accepted files');
    }

    // If user initiated upload from Library, refresh list immediately so "processing" rows appear without a full page refresh.
    if (STATE.currentView === 'library') {
      try { initLibrary(); } catch {}
    }

    // Poll only the first doc so the progress bar remains meaningful.
    if (data.accepted?.[0]?.status === 'ready' || data.accepted_files?.[0]?.status === 'ready' ) {
      setProgress(100, 'Done!');
      if (libFill) libFill.style.width = '100%';
      if (libLbl) libLbl.textContent = 'Done!';
      setTimeout(onDocReady, 700);
    } else {
      pollStatus();
    }
  } catch (e) {
    setUploadFeedback(e.message, true);
    s('progressSection', 'none');
    if (libFb) { libFb.textContent = e.message; libFb.className = 'lib-upload-fb error'; }
    if (libProg) libProg.style.display = 'none';
  }
}

async function uploadFile(file) {
  setUploadFeedback(`Uploading "${file.name}"…`);
  setProgress(20, 'Uploading…');

  const fname = el('topbarFilename');
  if (fname) fname.textContent = file.name;

  const fd = new FormData();
  fd.append('file', file);
  fd.append('user_id', STATE.userId || 'guest');

  try {
    const res = await fetch('/api/upload', { method:'POST', body:fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');
    if (STATE.docId !== data.doc_id) resetRefreshBundle();
    STATE.docId = data.doc_id;
    STATE.docFilename = data.filename || file.name;
    if (data.status === 'ready') {
      onDocReady();
    } else {
      pollStatus();
    }
  } catch(e) {
    setUploadFeedback(e.message, true);
    s('progressSection','none');
  }
}

async function pollStatus() {
  setProgress(55, 'Processing document…');
  try {
    const d = await get(`status/${STATE.docId}`);
    if (d.status === 'ready') {
      setProgress(100, 'Done!');
      setTimeout(onDocReady, 700);
    } else if (d.status === 'failed') {
      throw new Error(d.error || 'Processing failed');
    } else {
      // No fake progress: interpret progress based on `status`, not only `processing_stage`.
      let pct = 40;
      if (d.status === 'partially_ready') {
        pct = 70; // embeddings/vector ready
      } else if (d.status === 'processing') {
        if (d.processing_stage === 'uploaded' || d.processing_stage === 'parsed') pct = 20;      // parsing
        else if (d.processing_stage === 'structured' || d.processing_stage === 'embedded') pct = 40; // chunking
        else if (d.processing_stage === 'indexed') pct = 70; // embeddings done, BM25/indexing may still run
      }
      setProgress(pct, `Stage: ${d.processing_stage || 'processing'}…`);
      setTimeout(pollStatus, 3000);
    }
  } catch(e) {
    setUploadFeedback(e.message, true);
    s('progressSection','none');
  }
}

function onDocReady() {
  _saveDocState();
  fetchScore();
  const sb = el('topbarStatus');
  if (sb) sb.textContent = 'READY';
  const fn = el('topbarFilename');
  if (fn) fn.textContent = STATE.docFilename || STATE.docId || 'Document';
  // If we're on the separate upload view, switch to app
  if (el('uploadView')?.style.display !== 'none') {
    showApp();
  } else {
    // Already inside app — just refresh library
    initLibrary();
  }
}

function setUploadFeedback(msg, isErr=false) {
  const fb = el('uploadFeedback');
  if (!fb) return;
  fb.textContent = msg;
  fb.className = 'upload-feedback' + (isErr ? ' error' : '');
}

function setProgress(pct, label) {
  s('progressSection','block');
  const fill = el('progressFill');
  const lbl  = el('progressLabel');
  if (fill) fill.style.width = pct+'%';
  if (lbl)  lbl.textContent  = label || '';
}

// ── NAVIGATION ────────────────────────────────────────────────
let _searchMode = 'keyword';
let _suggestTimer = null;
let _suggestActiveIndex = -1;
let _suggestPointerDown = false; // prevents blur handler hiding dropdown during selection
let _libraryRefreshTimer = null;

function go(viewId) {
  STATE.currentView = viewId;
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.view === viewId);
  });
  document.querySelectorAll('.view').forEach(v => v.classList.remove('view-active'));
  const vEl = el('view' + cap(viewId));
  if (vEl) vEl.classList.add('view-active');

  if (viewId === 'quiz'       && needsLoad('quizContent'))       initQuiz();
  if (viewId === 'mocktest'   && needsLoad('mocktestContent'))   initMockTest();
  if (viewId === 'flashcards' && needsLoad('flashcardsContent')) initFlashcards();
  if (viewId === 'summary'    && needsLoad('summaryContent'))    initSummary();
  if (viewId === 'leaderboard') initLeaderboard();
  if (viewId === 'weakness')    initWeakness();
  if (viewId === 'library')     initLibrary();
  if (viewId === 'evaluation')  resetEvaluation();
  if (viewId === 'payments')    initPayments();

  // On mobile, auto-close the sidebar after navigating so the main content is visible again.
  if (window.innerWidth <= 768) {
    const sb = el('sidebar');
    if (sb) sb.classList.remove('open');
  }
}

function needsLoad(containerId) {
  const c = el(containerId);
  return c && (c.querySelector('.skeleton-block') || c.querySelector('.empty-state'));
}

function toggleSidebar() {
  el('sidebar')?.classList.toggle('open');
}

// ── ASK AI ───────────────────────────────────────────────────
async function sendMsg() {
  const input = el('chatInput');
  const qRaw = input.value.trim();
  let q = qRaw;
  if (!q || !STATE.userId) return;
  const isExplainFollowup = /^(?:pls|please)?\s*(?:can you\s*)?(?:explain|simplify|describe|rephrase)(?:\s+this|\s+it)?(?:\s+in\s+detail)?\s*$/i.test(qRaw);
  if (isExplainFollowup) {
    if (STATE.lastAskTopic) {
      q = `Explain this topic from my documents in simple terms: ${STATE.lastAskTopic}`;
    } else if (STATE.lastAskQuery) {
      q = `Explain this from my documents in simple terms: ${STATE.lastAskQuery}`;
    }
  }
  input.value = '';

  appendMsg('user', q);
  const aiId = 'ai-' + Date.now();
  appendMsg('ai', `<span class="btn-spinner btn-spinner-dark"></span>`, aiId);

  try {
    const d = await api('ask', {
      query: q,
      user_id: STATE.userId,
      llm_variant: getLlmVariant(),
    });
    const srcList = d.sources || d.source_chunks || [];
    const firstTopic = (srcList[0]?.section || '').replace(/\*\*/g, '').trim();
    if (firstTopic) STATE.lastAskTopic = firstTopic;
    STATE.lastAskQuery = q;
    const conf = d.confidence_label || (d.confidence && d.confidence.level) || '';
    const confHtml = conf
      ? `<span class="source-chip conf-chip" title="Confidence">${esc(conf)}</span>`
      : '';
    const srcHtml = srcList.length
      ? `<div class="msg-sources">${confHtml}${srcList.map(function(c) {
          var sec = (c.section || c.preview || '').replace(/\*\*/g, '');
          var label = (sec || 'Source');
          return `<span class="source-chip">📎 ${esc(label)}</span>`;
        }).join('')}</div>`
      : (confHtml ? `<div class="msg-sources">${confHtml}</div>` : '');
    updateMsg(aiId, renderMd(d.answer) + srcHtml);
    fetchScore();
  } catch(e) {
    updateMsg(aiId, `<span style="color:var(--danger)">${e.message}</span>`);
  }
}

function appendMsg(role, html, id='') {
  const box = el('chatMessages');
  const empty = box.querySelector('.chat-empty');
  if (empty) empty.remove();

  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  if (id) div.id = id;
  div.innerHTML = `<div class="msg-bubble">${html}</div>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function updateMsg(id, html) {
  const m = el(id);
  if (m) { m.querySelector('.msg-bubble').innerHTML = html; el('chatMessages').scrollTop = 9999; }
}

// ── QUIZ ─────────────────────────────────────────────────────
async function initQuiz() {
  if (!requireDoc('quizContent')) return;
  await loadQuizType('quiz', 'quizContent');
}
async function initMockTest() {
  if (!requireDoc('mocktestContent')) return;
  await loadQuizType('mock_test', 'mocktestContent');
}

async function loadQuizType(type, containerId, opts = {}) {
  const container = el(containerId);
  const refresh = opts.refresh === true;
  container.innerHTML = skeletonBlocks(3);
  try {
    const body = { doc_id: STATE.docId, user_id: STATE.userId, quiz_type: type };
    if (refresh) {
      body.refresh = true;
      const ex = getRefreshPayload(type);
      if (ex.previous_output) body.previous_output = ex.previous_output;
      if (ex.source_chunk_ids?.length) body.source_chunk_ids = ex.source_chunk_ids;
    }
    const d = await api('quiz/start', body);
    STATE.currentQuiz = d.questions;
    const quizKey = type === 'mock_test' ? 'mock' : 'quiz';
    STATE.quizByKey[quizKey] = d.questions || [];
    STATE.quizAnswers[quizKey] = {};
    STATE.currentQuizMeta = { containerId, quizKey };
    captureFeatureContext(type, d);
    try {
      STATE.refreshBundle[type].previous_output = JSON.stringify(d.questions || []);
    } catch (_) {}
    const mainId = type === 'mock_test' ? 'mocktestMain' : 'quizMain';
    const inner = renderQuiz(d.questions, type === 'mock_test', quizKey);
    container.innerHTML = `<div class="feature-body" id="${mainId}">${inner}</div>`;
  } catch(e) {
    container.innerHTML = errorState(e.message);
  }
}

function renderQuiz(questions, isMock=false, quizKey='quiz') {
  if (!questions?.length) return errorState('No questions generated.');

  const letters = ['A','B','C','D'];
  const submitTarget = isMock ? 'mocktestContent' : 'quizContent';
  const submitLabel = isMock ? 'Mock Test' : 'Quiz';
  const qHtml = questions.map((q,i) => {
    const qText = q.question || q.q || '';
    const qDiff = q.difficulty || 'easy';
    const qOpts = q.options || [];
    const qid = String(q.question_id || q.id || `q_${i}`);
    return `
    <div class="q-card" id="qc_${quizKey}_${i}">
      <div class="q-card-header">
        <div>
          <div class="q-text">${i+1}. ${esc(qText)}</div>
          ${isMock && q.topic ? `<div class="q-meta-topic">Topic: ${esc(q.topic)}</div>` : ''}
        </div>
        <span class="q-badge badge-${qDiff.toLowerCase()}">${qDiff.toUpperCase()}</span>
      </div>
      <div class="q-options">
        ${qOpts.slice(0,4).map((opt,j) => `
          <div class="q-option" id="opt_${quizKey}_${i}_${j}" data-qid="${esc(qid)}" onclick="selectOpt('${quizKey}',${i},${j})">
            <input type="radio" name="q_${quizKey}_${i}" value="${letters[j]}" />${letters[j]}. ${esc(
              String(opt || '').replace(/^[A-D][\)\.\:\-]\s*/i,'')
            )}
          </div>
        `).join('')}
      </div>
      <div class="q-explanation" id="exp_${quizKey}_${i}"></div>
    </div>
  `}).join('');

  return `<div>${qHtml}
    <button class="btn btn-primary submit-quiz-btn" onclick="submitQuiz('${submitTarget}','${quizKey}')">
      Submit ${submitLabel}
    </button></div>`;
}

function selectOpt(quizKey, qi, oi) {
  // Clear selected visuals for this question.
  document.querySelectorAll(`[id^="opt_${quizKey}_${qi}_"]`).forEach(d => d.classList.remove('selected'));
  const opt = el(`opt_${quizKey}_${qi}_${oi}`);
  if (!opt) return;
  opt.classList.add('selected');
  const radio = opt.querySelector('input');
  if (radio) radio.checked = true;
  const qid = opt.dataset.qid || `q_${qi}`;
  const selectedValue = (radio?.value || '').trim();
  STATE.quizAnswers[quizKey] = STATE.quizAnswers[quizKey] || {};
  STATE.quizAnswers[quizKey][qid] = selectedValue;
}

async function submitQuiz(containerId, quizKey='quiz') {
  const questions = (STATE.quizByKey && STATE.quizByKey[quizKey]) || STATE.currentQuiz || [];
  if (!questions.length) return;
  const container = el(containerId);
  const selectedByQid = STATE.quizAnswers[quizKey] || {};
  const answers = questions.map((q, i) => {
    const qid = String(q.question_id || q.id || `q_${i}`);
    const fromState = (selectedByQid[qid] || '').trim();
    if (fromState) return fromState;
    const selected = container?.querySelector(`[id^="opt_${quizKey}_${i}_"].selected input`);
    return (selected?.value || '').trim();
  });
  console.log('[QUIZ SUBMIT]', quizKey, { answers });
  if (answers.some(a => !a)) {
    alert('Please select an option for all questions before submitting.');
    return;
  }

  try {
    const quizType = containerId === 'mocktestContent' ? 'mock_test' : 'quiz';
    const d = await api('quiz/submit', {
      doc_id: STATE.docId, user_id: STATE.userId,
      questions, answers,
      quiz_type: quizType,
    });

    // details array from evaluate_quiz
    const evals = d.details || d.evaluations || [];
    questions.forEach((q,i) => {
      const res = evals[i] || {};
      const correctAns = (q.correct_answer || res.correct_answer || '').trim().toUpperCase();
      container.querySelectorAll(`[id^="opt_${quizKey}_${i}_"]`).forEach(div => {
        div.style.pointerEvents='none';
        const v = (div.querySelector('input')?.value || '').trim();
        const optLetter = v.toUpperCase();
        if (optLetter === correctAns) {
          div.classList.add('correct');
        } else if (div.classList.contains('selected') && !res.is_correct) {
          div.classList.add('wrong');
        }
      });
      const expEl = el(`exp_${quizKey}_${i}`);
      if (expEl) {
        const uaLetter = (res.user_answer_letter || res.user_answer || '').toString().trim().toUpperCase();
        const uaText = (res.user_answer_text || '').toString();
        const caLetter = (res.correct_answer || correctAns || '').toString().trim().toUpperCase();
        const caText = (res.correct_answer_text || '').toString();
        const explanation = (res.explanation || q.explanation || '').toString();
        expEl.innerHTML = `
          <div class="quiz-result-lines">
            <div><strong>Your answer:</strong> ${esc(uaLetter || '—')}${uaText ? ` — ${esc(uaText)}` : ''}</div>
            <div><strong>Correct answer:</strong> ${esc(caLetter || '—')}${caText ? ` — ${esc(caText)}` : ''}</div>
          </div>
          ${explanation ? `<details class="quiz-explain-details"><summary>Show explanation</summary>
            <div class="quiz-explain-body">${esc(explanation)}</div></details>` : ''}`;
        expEl.style.display='block';
      }
    });

    // Prepend score banner
    const pct = Math.round(d.accuracy*100);
    const banner = document.createElement('div');
    banner.className='score-banner';
    banner.innerHTML = `
      <div class="score-num">${d.correct}<span> / ${d.total}</span></div>
      <div class="score-msg">You scored ${pct}%${pct>=80?' 🎉':pct>=50?' Keep it up!':' Keep practicing!'}</div>
    `;
    const wrapId = containerId === 'mocktestContent' ? 'mocktestMain' : 'quizMain';
    const wrap = el(wrapId);
    const target = wrap?.firstElementChild || container.querySelector('.feature-body')?.firstElementChild;
    if (target) target.prepend(banner);
    else container.querySelector('div')?.prepend(banner);
    container.querySelector('.submit-quiz-btn')?.remove();
    fetchScore();
  } catch(e) { alert('Submission failed: ' + e.message); }
}

// ── FLASHCARDS ───────────────────────────────────────────────
async function initFlashcards(opts = {}) {
  if (!requireDoc('flashcardsContent')) return;
  const container = el('flashcardsContent');
  const refresh = opts.refresh === true;
  container.innerHTML = `<div class="skeleton-block tall"></div>`;
  try {
    const body = { doc_id: STATE.docId, user_id: STATE.userId, content_type: 'flashcards' };
    if (refresh) {
      body.refresh = true;
      const ex = getRefreshPayload('flashcards');
      if (ex.previous_output) body.previous_output = ex.previous_output;
      if (ex.source_chunk_ids?.length) body.source_chunk_ids = ex.source_chunk_ids;
    }
    const d = await api('generate', body);
    if (d.error) throw new Error(d.error);
    let cards = d.flashcards || d.content?.flashcards || [];

    // If API returned raw text, try to parse it
    if (!cards.length && d.raw) {
      cards = parseRawFlashcards(d.raw);
    }

    if (!cards?.length) throw new Error('No flashcards generated. Try uploading a more detailed document.');
    STATE._flashcards = cards; STATE._fcIdx = 0;
    captureFeatureContext('flashcards', d);
    try {
      STATE.refreshBundle.flashcards.previous_output = JSON.stringify(cards);
    } catch (_) {}
    renderFcView(container);
  } catch(e) { container.innerHTML = errorState(e.message); }
}

function parseRawFlashcards(raw) {
  const cards = [];
  // Try JSON extraction first
  try {
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      if (parsed.flashcards) return parsed.flashcards;
    }
  } catch(e) {}

  // Try Q: / A: pattern
  const pairs = raw.split(/\n\s*\n/).filter(b => b.trim());
  for (const block of pairs) {
    const qMatch = block.match(/(?:Q|Question|Front)[:\s]+(.+)/i);
    const aMatch = block.match(/(?:A|Answer|Back)[:\s]+(.+)/i);
    if (qMatch && aMatch) cards.push({ q: qMatch[1].trim(), a: aMatch[1].trim() });
  }

  // Try numbered pattern: 1. Question - Answer
  if (!cards.length) {
    const lines = raw.split('\n').filter(l => l.trim());
    for (const line of lines) {
      const m = line.match(/^\d+[\.\)]\s*(.+?)\s*[-–—]\s*(.+)$/);
      if (m) cards.push({ q: m[1].trim(), a: m[2].trim() });
    }
  }
  return cards;
}

function renderFcView(container) {
  const cards = STATE._flashcards;
  const idx   = STATE._fcIdx;
  const card  = cards[idx];
  container.innerHTML = `
    <div class="fc-wrap">
      <div class="fc" id="fcCard" onclick="this.classList.toggle('flipped')">
        <div class="fc-face fc-front">${esc(card.q || card.front || '')}</div>
        <div class="fc-face fc-back">
          ${esc(card.a || card.back || '')}
        </div>
      </div>
    </div>
    <div class="fc-controls">
      <button class="btn btn-ghost btn-sm" onclick="fcNav(-1)" ${idx===0?'disabled':''}>← Prev</button>
      <span class="fc-counter">${idx+1} / ${cards.length}</span>
      <button class="btn btn-primary btn-sm" onclick="fcNav(1)" ${idx===cards.length-1?'disabled':''}>Next →</button>
    </div>
    <p style="text-align:center;font-size:13px;color:var(--text-3);margin-top:12px">Click the card to flip</p>
  `;
}

function fcNav(dir) {
  const newIdx = STATE._fcIdx + dir;
  if (newIdx < 0 || newIdx >= STATE._flashcards.length) return;
  STATE._fcIdx = newIdx;
  renderFcView(el('flashcardsContent'));
}

// ── SUMMARY ──────────────────────────────────────────────────
async function initSummary(opts = {}) {
  if (!requireDoc('summaryContent')) return;
  const container = el('summaryContent');
  const refresh = opts.refresh === true;
  container.innerHTML = `<div class="skeleton-block"></div><div class="skeleton-block"></div><div class="skeleton-block tall"></div>`;
  try {
    const body = { doc_id: STATE.docId, user_id: STATE.userId, content_type: 'summary' };
    if (refresh) {
      body.refresh = true;
      const ex = getRefreshPayload('summary');
      if (ex.previous_output) body.previous_output = ex.previous_output;
      if (ex.source_chunk_ids?.length) body.source_chunk_ids = ex.source_chunk_ids;
    }
    const d = await api('generate', body);
    if (d.error) throw new Error(d.error);
    // summary endpoint returns {bullets: [...], explanation: "..."} (strict)
    let html = '';

    if (d.bullets?.length) {
      const exp = d.explanation ? `<p>${esc(d.explanation)}</p>` : '';
      html = `${exp}<ul>${d.bullets.map(b => `<li>${esc(b)}</li>`).join('')}</ul>`;
    } else if (d.summary) {
      html = `<p>${esc(d.summary)}</p>`;
      if (d.bullets?.length) {
        html += '<ul>' + d.bullets.map(b => `<li>${esc(b)}</li>`).join('') + '</ul>';
      }
    } else {
      html = renderMd(d.content || d.raw || 'No summary generated.');
    }
    captureFeatureContext('summary', d);
    const bulletTxt = (d.bullets || []).join('\n');
    STATE.refreshBundle.summary.previous_output = [bulletTxt, d.explanation || ''].filter(Boolean).join('\n\n').slice(0, 12000);
    container.innerHTML = `<div class="summary-box">${html}</div>`;
  } catch(e) { container.innerHTML = errorState(e.message); }
}

// ── LEADERBOARD ──────────────────────────────────────────────
async function initLeaderboard() {
  const container = el('leaderboardContent');
  container.innerHTML = `<div class="skeleton-block"></div><div class="skeleton-block"></div><div class="skeleton-block"></div>`;
  try {
    const d = await get('leaderboard');
    const me = STATE.username || STATE.email || '';
    if (!d.leaderboard?.length) {
      container.innerHTML = '<div class="empty-state"><p>No entries yet — complete a quiz to appear here!</p></div>';
      return;
    }
    container.innerHTML = `<div class="lb-list">` +
      d.leaderboard.map(u => {
        const isMe = u.username === me || u.user_id === STATE.userId;
        const rankClass = u.rank <= 3 ? `rank-${u.rank}` : '';
        return `<div class="lb-row ${rankClass} ${isMe?'is-me':''}">
          <div class="lb-rank">${rankEmoji(u.rank)}</div>
          <div class="lb-name">${esc(u.username||u.user_id)} ${isMe?'<span class="lb-you-tag">You</span>':''}</div>
          <div class="lb-xp">${u.daily_xp} XP</div>
        </div>`;
      }).join('') + `</div>
      <p style="text-align:center;font-size:12px;color:var(--text-3);margin-top:16px">Resets daily at midnight</p>`;
  } catch(e) { container.innerHTML = errorState(e.message); }
}

function rankEmoji(r) {
  if (r===1) return '🥇';
  if (r===2) return '🥈';
  if (r===3) return '🥉';
  return `#${r}`;
}

// ── UTILITIES ─────────────────────────────────────────────────

function el(id)   { return document.getElementById(id); }
function val(id)  { return el(id)?.value || ''; }
function s(id, d) { const e=el(id); if(e) e.style.display=d; }
function setText(id, text) { const e=el(id); if(e) e.textContent=text; }
function setErr(id, msg)   { const e=el(id); if(e) e.textContent=msg; }
function cap(str)  { return str.charAt(0).toUpperCase() + str.slice(1); }
function isEmail(v){ return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }
function esc(s)    { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function persist() {
  localStorage.setItem('intellirag_uid',   STATE.userId||'');
  localStorage.setItem('intellirag_name',  STATE.username||'');
  localStorage.setItem('intellirag_email', STATE.email||'');
}

function setBtnLoading(id, loading) {
  const btn = el(id);
  if (!btn) return;
  btn.disabled = loading;
  const t = btn.querySelector('.btn-text');
  const l = btn.querySelector('.btn-loading');
  if (t) t.style.display = loading ? 'none' : '';
  if (l) l.style.display = loading ? '' : 'none';
  if (loading && !l) btn.innerHTML = `<span class="btn-spinner"></span>`;
}

function skeletonBlocks(n) {
  return Array.from({length:n}, ()=>'<div class="skeleton-block"></div>').join('');
}

function errorState(msg) {
  return `<div class="empty-state">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
    <p>${esc(msg)}</p>
  </div>`;
}

// Robust markdown renderer with math support (marked + KaTeX)
function renderMd(text) {
  if (typeof text !== 'string') return String(text || '');

  // Normalize line endings
  let src = text.replace(/\r\n/g, '\n');

  // Placeholders for math blocks
  const mathBlocks = [];
  const mathInlines = [];

  // 1. Extract block math: $$ math $$
  src = src.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
    const key = `@@MATH_BLOCK_${mathBlocks.length}@@`;
    mathBlocks.push(math.trim());
    return key;
  });

  // 2. Extract inline math: $ math $
  src = src.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
    const key = `@@MATH_INLINE_${mathInlines.length}@@`;
    mathInlines.push(math.trim());
    return key;
  });

  // Parse markdown
  let html = '';
  if (typeof marked !== 'undefined' && marked.parse) {
    try {
      html = marked.parse(src);
    } catch (e) {
      console.error("Marked parsing failed, fallback used", e);
      html = fallbackRenderMd(src);
    }
  } else {
    html = fallbackRenderMd(src);
  }

  // Helper function to render LaTeX or return fallback text
  function renderLatex(math, displayMode) {
    if (typeof katex !== 'undefined' && katex.renderToString) {
      try {
        return katex.renderToString(math, { displayMode, throwOnError: false });
      } catch (err) {
        console.error(err);
        return displayMode ? `<pre>$$${math}$$</pre>` : `<code>$${math}$</code>`;
      }
    }
    return displayMode ? `<pre class="math-block">$$${math}$$</pre>` : `<code class="math-inline">$${math}$</code>`;
  }

  // 3. Restore block math
  mathBlocks.forEach((math, idx) => {
    const rendered = renderLatex(math, true);
    html = html.replace(`@@MATH_BLOCK_${idx}@@`, rendered);
  });

  // 4. Restore inline math
  mathInlines.forEach((math, idx) => {
    const rendered = renderLatex(math, false);
    html = html.replace(`@@MATH_INLINE_${idx}@@`, rendered);
  });

  return html;
}

function fallbackRenderMd(text) {
  let h = esc(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g,     '<em>$1</em>')
    .replace(/`(.*?)`/g,       '<code>$1</code>')
    .replace(/^### (.+)$/gm,   '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,    '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,     '<h1>$1</h1>')
    .replace(/^- (.+)$/gm,     '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n\n/g,           '</p><p>')
    .replace(/\n/g,             '<br>');
  if (!h.startsWith('<h') && !h.startsWith('<ul')) h = `<p>${h}</p>`;
  return h;
}


// ── API HELPERS ───────────────────────────────────────────────
const _LLM_API_ENDPOINTS = new Set(['ask', 'mentor', 'generate', 'quiz/start', 'search']);

async function api(endpoint, body) {
  let payload = body || {};
  if (typeof payload === 'object' && _LLM_API_ENDPOINTS.has(endpoint)) {
    payload = { ...payload, llm_variant: getLlmVariant() };
  }
  if (typeof payload === 'object' && !payload.user_id && STATE.userId) {
    payload.user_id = STATE.userId;
  }
  
  const headers = {'Content-Type':'application/json'};
  if (STATE.userId) {
    headers['X-User-ID'] = STATE.userId;
  }
  
  const res = await fetch('/api/' + endpoint, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(payload),
  });
  
  if (res.status === 429 || res.status === 403) {
    let msg = `Access denied (${res.status})`;
    try {
      const data = await res.json();
      msg = data.detail || data.message || msg;
    } catch (_) {}
    showPaymentsAlert(msg);
    go('payments');
    throw new Error(msg);
  }
  
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.message || `Request failed (${res.status})`);
  return data;
}

async function get(endpoint) {
  const headers = {};
  if (STATE.userId) {
    headers['X-User-ID'] = STATE.userId;
  }
  const res = await fetch('/api/' + endpoint, {
    headers: headers
  });
  
  if (res.status === 429 || res.status === 403) {
    let msg = `Access denied (${res.status})`;
    try {
      const data = await res.json();
      msg = data.detail || data.message || msg;
    } catch (_) {}
    showPaymentsAlert(msg);
    go('payments');
    throw new Error(msg);
  }
  
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.message || `Request failed (${res.status})`);
  return data;
}

function showPaymentsAlert(msg) {
  const banner = el('paymentsAlertBanner');
  if (banner) {
    banner.textContent = msg;
    banner.style.display = 'flex';
    banner.style.transform = 'scale(1.02)';
    setTimeout(() => { banner.style.transform = ''; }, 200);
    const view = el('viewPayments');
    if (view) {
      view.scrollIntoView({ behavior: 'smooth' });
    }
  }
}

async function initPayments() {
  const grid = el('usageStatsGrid');
  if (!grid) return;
  
  grid.innerHTML = '<div class="skeleton-block"></div>';
  
  try {
    const data = await get('users/profile');
    STATE.tier = data.tier;
    
    // Sync sidebar upgrade card
    const upCard = el('sidebarUpgradeCard');
    if (upCard) {
      upCard.style.display = data.tier === 'free' ? 'flex' : 'none';
    }
    
    // Sync active plan buttons styling
    const btnFree = el('btnPlanFree');
    const btnStandard = el('btnPlanStandard');
    const btnPremium = el('btnPlanPremium');
    
    const cardFree = el('planCardFree');
    const cardStandard = el('planCardStandard');
    const cardPremium = el('planCardPremium');
    
    // Reset cards and buttons
    [cardFree, cardStandard, cardPremium].forEach(c => c?.classList.remove('active-plan'));
    if (btnFree) { btnFree.disabled = false; btnFree.textContent = 'Switch to Freemium'; btnFree.className = 'btn btn-ghost btn-full plan-btn'; }
    if (btnStandard) { btnStandard.disabled = false; btnStandard.textContent = 'Upgrade to Standard'; btnStandard.className = 'btn btn-primary btn-full plan-btn'; }
    if (btnPremium) { btnPremium.disabled = false; btnPremium.textContent = 'Upgrade to Premium'; btnPremium.className = 'btn btn-premium btn-full plan-btn'; }
    
    if (data.tier === 'free') {
      cardFree?.classList.add('active-plan');
      if (btnFree) { btnFree.disabled = true; btnFree.textContent = 'Active Plan'; btnFree.className = 'btn btn-secondary btn-full plan-btn'; }
    } else if (data.tier === 'standard') {
      cardStandard?.classList.add('active-plan');
      if (btnStandard) { btnStandard.disabled = true; btnStandard.textContent = 'Active Plan'; btnStandard.className = 'btn btn-secondary btn-full plan-btn'; }
    } else if (data.tier === 'premium') {
      cardPremium?.classList.add('active-plan');
      if (btnPremium) { btnPremium.disabled = true; btnPremium.textContent = 'Active Plan'; btnPremium.className = 'btn btn-secondary btn-full plan-btn'; }
    }
    
    // Render progress bars
    grid.innerHTML = '';
    const features = [
      { key: 'rag', label: 'Ask AI (RAG)', icon: '💬' },
      { key: 'quiz', label: 'Quizzes & Mock Tests', icon: '❓' },
      { key: 'flashcard', label: 'Flashcards', icon: '🎴' },
      { key: 'summary', label: 'Summaries', icon: '📝' }
    ];
    
    features.forEach(f => {
      const usage = data.usage[f.key];
      const used = usage.used;
      const limit = usage.limit;
      const tierLabel = data.tier === 'free' ? `${used} / ${limit}` : `${used} / ∞`;
      const pct = data.tier === 'free' ? Math.min(100, (used / limit) * 100) : 0;
      
      let statusClass = 'safe';
      if (data.tier === 'free') {
        if (pct >= 90) statusClass = 'danger';
        else if (pct >= 50) statusClass = 'warn';
      }
      
      const card = document.createElement('div');
      card.className = 'usage-stat-card';
      card.innerHTML = `
        <div class="usage-stat-header">
          <span>${f.icon} ${f.label}</span>
          <span>${tierLabel}</span>
        </div>
        <div class="usage-stat-val">${used}</div>
        <div class="usage-bar-track">
          <div class="usage-bar-fill ${statusClass}" style="width: ${pct}%"></div>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Failed to load profile details:', err);
    grid.innerHTML = `<div class="error-state"><p>Error loading daily usage: ${err.message}</p></div>`;
  }
}

async function subscribeToPlan(tier) {
  if (!STATE.userId) {
    alert('Please sign in first.');
    return;
  }
  
  let btnId = '';
  if (tier === 'standard') btnId = 'btnPlanStandard';
  else if (tier === 'premium') btnId = 'btnPlanPremium';
  else if (tier === 'free') btnId = 'btnPlanFree';
  
  if (btnId) setBtnLoading(btnId, true);
  
  try {
    const res = await api('payments/subscribe', { user_id: STATE.userId, tier: tier });
    STATE.tier = res.tier;
    
    const alertBanner = el('paymentsAlertBanner');
    if (alertBanner) {
      alertBanner.style.display = 'none';
      alertBanner.textContent = '';
    }
    
    await initPayments();
    
    const card = el(`planCard${cap(tier)}`);
    if (card) {
      card.style.transform = 'scale(1.03)';
      setTimeout(() => { card.style.transform = ''; }, 300);
    }
    
    updateUserUI();
  } catch (err) {
    alert(`Failed to subscribe: ${err.message}`);
  } finally {
    if (btnId) setBtnLoading(btnId, false);
  }
}

// ── SEARCH ENGINE ─────────────────────────────────────────────
function setSearchMode(mode, btn) {
  _searchMode = mode;
  document.querySelectorAll('.mode-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  el('searchModeLabel').innerHTML = `Mode: <strong>${mode}</strong>`;
}

async function doSearch() {
  const q = el('searchInput').value.trim();
  if (!q) return;

  const btn = el('searchBtn');
  btn.disabled = true; btn.textContent = 'Searching…';
  el('searchResults').innerHTML = skeletonBlocks(3);

  try {
    const d = await api('search/user', { user_id: STATE.userId, query: q, mode: _searchMode, limit: 30 });
    renderSearchResults(d, q);
  } catch(e) {
    el('searchResults').innerHTML = errorState(e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Search';
  }
}

async function fetchSearchSuggestions() {
  const inputEl = el('searchInput');
  const q = (inputEl?.value || '').trim();
  let box = el('searchSuggestBox');
  if (!box) {
    const wrap = inputEl?.closest('.search-input-wrap');
    if (wrap) {
      box = document.createElement('div');
      box.id = 'searchSuggestBox';
      box.className = 'sr-suggest-box';
      wrap.appendChild(box);
      // Ensure the dropdown overlays nicely.
      if (!wrap.style.position) wrap.style.position = 'relative';
    }
  }
  if (!box) return;

  if (!q || q.length < 2 || !STATE.userId) {
    box.style.display = 'none';
    box.innerHTML = '';
    _suggestActiveIndex = -1;
    return;
  }

  try {
    const d = await get(`search/suggest/user/${encodeURIComponent(STATE.userId)}?q=${encodeURIComponent(q)}&limit=5`);
    const suggestions = d.suggestions || [];
    if (!suggestions.length) {
      box.style.display = 'none';
      box.innerHTML = '';
      _suggestActiveIndex = -1;
      return;
    }
    box.innerHTML = suggestions.map((s, idx) => {
      const label = _highlightSuggestTerm(s, q);
      // Explicit onclick so click binding can never "disappear" due to bubbling/timing.
      return `<button type="button" class="sr-suggest-item" data-suggest="${esc(s)}" data-idx="${idx}" onclick="onSuggestItemClick(event, this)">${label}</button>`;
    }).join('');
    box.style.display = 'block';
    _suggestActiveIndex = -1;
  } catch (e) {
    box.style.display = 'none';
    _suggestActiveIndex = -1;
  }
}

function _highlightSuggestTerm(term, query) {
  const t = esc(term);
  const q = String(query || '').trim();
  if (!q) return t;
  const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
  return t.replace(regex, '<mark class="sr-suggest-mark">$1</mark>');
}

function _getVisibleSuggestItems() {
  const box = el('searchSuggestBox');
  if (!box || box.style.display === 'none') return [];
  return Array.from(box.querySelectorAll('.sr-suggest-item'));
}

function _setSuggestActive(index) {
  const items = _getVisibleSuggestItems();
  if (!items.length) {
    _suggestActiveIndex = -1;
    return;
  }
  if (index < 0) index = items.length - 1;
  if (index >= items.length) index = 0;
  _suggestActiveIndex = index;
  items.forEach((it, i) => it.classList.toggle('active', i === _suggestActiveIndex));
}

function _applySuggestion(value, triggerSearch = true) {
  const si = el('searchInput');
  if (!si) return;
  si.value = value || '';
  // Force google-style suggestions to run in hybrid mode.
  if (_searchMode !== 'hybrid') {
    _searchMode = 'hybrid';
    const ml = el('searchModeLabel');
    if (ml) ml.innerHTML = `Mode: <strong>hybrid</strong>`;
  }
  const box = el('searchSuggestBox');
  if (box) {
    box.style.display = 'none';
    box.innerHTML = '';
  }
  _suggestActiveIndex = -1;
  _suggestPointerDown = false;
  if (triggerSearch) doSearch();
}

function onSuggestItemClick(e, btnEl) {
  e?.preventDefault?.();
  e?.stopPropagation?.();
  const val = (btnEl?.dataset?.suggest || '').toString();
  console.log('Clicked suggestion:', val);
  _suggestPointerDown = false;
  _applySuggestion(val, true);
}

function onDidYouMeanClick(e, linkEl) {
  e?.preventDefault?.();
  e?.stopPropagation?.();
  const raw = (linkEl?.dataset?.q || '').toString();
  const val = decodeURIComponent(raw || '');
  _applySuggestion(val, true);
}

function onSearchResultCardClick(e, cardEl) {
  if (e?.target?.closest?.('button')) return;
  const docId = decodeURIComponent((cardEl?.dataset?.docId || '').toString());
  const page = Number(cardEl?.dataset?.page || '1') || 1;
  const query = decodeURIComponent((cardEl?.dataset?.query || '').toString());
  const snippet = decodeURIComponent((cardEl?.dataset?.snippet || '').toString());
  if (!docId) return;
  const q = new URLSearchParams();
  q.set('doc_id', docId);
  q.set('page', String(page));
  if (query) q.set('query', query);
  if (snippet) q.set('snippet', snippet);
  window.open(`/pdf-viewer.html?${q.toString()}`, '_blank', 'noopener');
}

function onOpenCourseFromSearch(e, btnEl) {
  e?.preventDefault?.();
  e?.stopPropagation?.();
  const docId = decodeURIComponent((btnEl?.dataset?.docId || '').toString());
  const docName = decodeURIComponent((btnEl?.dataset?.docName || '').toString());
  const nodeId = decodeURIComponent((btnEl?.dataset?.nodeId || '').toString());
  const chunkId = decodeURIComponent((btnEl?.dataset?.chunkId || '').toString());
  const query = decodeURIComponent((btnEl?.dataset?.query || '').toString());
  const snippet = decodeURIComponent((btnEl?.dataset?.snippet || '').toString());
  openCourseView(docId, docName, nodeId, chunkId, query, snippet);
}

function onOpenPdfFromSearch(e, btnEl) {
  e?.preventDefault?.();
  e?.stopPropagation?.();
  const docId = decodeURIComponent((btnEl?.dataset?.docId || '').toString());
  const page = Number(btnEl?.dataset?.page || '1') || 1;
  const query = decodeURIComponent((btnEl?.dataset?.query || '').toString());
  const snippet = decodeURIComponent((btnEl?.dataset?.snippet || '').toString());
  if (!docId) return;
  const q = new URLSearchParams();
  q.set('doc_id', docId);
  q.set('page', String(page));
  if (query) q.set('query', query);
  if (snippet) q.set('snippet', snippet);
  window.open(`/pdf-viewer.html?${q.toString()}`, '_blank', 'noopener');
}

function renderSearchResults(d, query) {
  const mode = d.mode || _searchMode;
  const results = d.results || [];
  const answer  = d.answer || '';
  const conf    = d.confidence;
  const sources = d.sources || [];
  const qInfo   = d.query_info || {};

  let html = '';

  // Meta bar
  html += `<div class="sr-meta">
    <span class="mode-badge mode-${mode}">${mode.toUpperCase()}</span>
    ${qInfo.query_type ? `<span class="sr-chip">Type: ${qInfo.query_type}</span>` : ''}
    ${qInfo.complexity ? `<span class="sr-chip">Complexity: ${qInfo.complexity}</span>` : ''}
    <span class="sr-chip">${results.length} result${results.length !== 1 ? 's' : ''}</span>
  </div>`;

  // "Did you mean?" typo correction suggestion
  if (d.did_you_mean) {
    const didYouMeanEncoded = encodeURIComponent(d.did_you_mean);
    html += `<div class="sr-typo-box">
      <span class="sr-typo-icon">💡</span>
      <span>Showing results for <a href="#" data-q="${didYouMeanEncoded}" onclick="onDidYouMeanClick(event,this)" class="sr-typo-link">${esc(d.did_you_mean)}</a></span>
      <span class="sr-typo-original">Search instead for: <em>${esc(d.original_query || query)}</em></span>
    </div>`;
  }

  // AI Answer (only in AI mode)
  if (answer) {
    const confScore = typeof conf === 'object' ? conf.score : conf;
    const confLevel = typeof conf === 'object' ? conf.level : (confScore > 0.7 ? 'high' : confScore > 0.4 ? 'medium' : 'low');
    html += `<div class="sr-ai-answer">
      <div class="sr-ai-header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
        AI Answer
        <span class="conf-badge conf-${confLevel}">${confLevel} confidence${confScore ? ' · ' + Math.round(confScore * 100) + '%' : ''}</span>
      </div>
      <div class="sr-ai-body">${renderMd(answer)}</div>
      ${sources.length ? `<div class="sr-sources">${sources.map(s => `<span class="source-chip">📎 ${esc(s.section || s)}</span>`).join('')}</div>` : ''}
    </div>`;
  }

  // Google-like result cards
  if (results.length) {
    html += `<div class="sr-results-list">`;
    results.forEach((r, i) => {
      const title = r.title || r.section || `Section ${i + 1}`;
      const snippet = _highlightTerms(r.snippet || r.text || '', query);
      const page = r.page || 1;
      const score = r.score || 0;
      const path = r.section_path || r.hierarchy_path || '';
      const docName = r.filename || r.doc_id || 'Document';
      const docId = r.doc_id || '';
      const dDocId = encodeURIComponent(docId);
      const dDocName = encodeURIComponent(docName);
      const dNodeId = encodeURIComponent(r.node_id || '');
      const dChunkId = encodeURIComponent(r.chunk_id || '');
      const dQuery = encodeURIComponent(query || '');
      const dSnippet = encodeURIComponent(r.snippet || r.text || '');
      html += `<div class="sr-google-card" role="button" tabindex="0"
        data-doc-id="${dDocId}" data-page="${page}" data-query="${dQuery}" data-snippet="${dSnippet}"
        onclick="onSearchResultCardClick(event,this)">
        <div class="sr-g-title">${esc(title)}</div>
        <div class="sr-g-url">📄 ${esc(docName)} · Page ${page} · Score: ${score}${path ? ' · ' + esc(path) : ''}</div>
        <div class="sr-g-snippet">${snippet}</div>
        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn btn-primary btn-sm" type="button"
            data-doc-id="${dDocId}"
            data-doc-name="${dDocName}"
            data-node-id="${dNodeId}"
            data-chunk-id="${dChunkId}"
            data-query="${dQuery}"
            data-snippet="${dSnippet}"
            onclick="onOpenCourseFromSearch(event,this)">
            Open in Course
          </button>
          <button class="btn btn-ghost btn-sm" type="button"
            data-doc-id="${dDocId}" data-page="${page}" data-query="${dQuery}" data-snippet="${dSnippet}"
            onclick="onOpenPdfFromSearch(event,this)">Open in PDF</button>
        </div>
      </div>`;
    });
    html += `</div>`;
  } else if (!answer) {
    html += `<div class="empty-state"><p>No results found for your query.</p></div>`;
  }

  el('searchResults').innerHTML = html;
}

// Wire live search suggestions
document.addEventListener('DOMContentLoaded', function() {
  const si = el('searchInput');
  if (!si) return;
  document.addEventListener('pointerdown', function(e) {
    const t = e.target;
    const btn = t?.closest?.('.sr-suggest-item');
    if (btn) _suggestPointerDown = true;
  });
  si.addEventListener('input', function() {
    if (_suggestTimer) clearTimeout(_suggestTimer);
    _suggestTimer = setTimeout(fetchSearchSuggestions, 180);
  });
  si.addEventListener('blur', function() {
    setTimeout(() => {
      const box = el('searchSuggestBox');
      // Don't hide dropdown if user is clicking inside it.
      if (box && !_suggestPointerDown) { box.style.display = 'none'; }
    }, 120);
  });
  si.addEventListener('focus', function() {
    fetchSearchSuggestions();
  });
  si.addEventListener('keydown', function(e) {
    const items = _getVisibleSuggestItems();
    if (!items.length) {
      if (e.key === 'Enter') {
        e.preventDefault();
        doSearch();
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      _setSuggestActive(_suggestActiveIndex + 1);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      _setSuggestActive(_suggestActiveIndex - 1);
      return;
    }
    if (e.key === 'Escape') {
      const box = el('searchSuggestBox');
      if (box) box.style.display = 'none';
      _suggestActiveIndex = -1;
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (_suggestActiveIndex >= 0 && _suggestActiveIndex < items.length) {
        _suggestPointerDown = false;
        onSuggestItemClick(e, items[_suggestActiveIndex]);
      } else {
        doSearch();
      }
    }
  });

  document.body.addEventListener('click', function(e) {
    // Fallback for older renders (should be redundant with per-button onclick).
    // Some browsers/targets may not support closest reliably; fall back to manual traversal.
    let btn = null;
    const t = e.target;
    if (t && typeof t.closest === 'function') {
      btn = t.closest('.sr-suggest-item');
    } else if (t && t instanceof Element) {
      let cur = t;
      while (cur && cur !== document.body) {
        if (cur.classList && cur.classList.contains('sr-suggest-item')) { btn = cur; break; }
        cur = cur.parentElement;
      }
    }
    if (!btn) return;
    e.stopPropagation();
    console.log('Clicked suggestion (fallback):', btn.dataset.suggest || '');
    _suggestPointerDown = false;
    _applySuggestion(btn.dataset.suggest || '', true);
  });
});

function _highlightTerms(text, query) {
  if (!query || !text) return esc(text);
  const escaped = esc(text);
  const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2);
  let result = escaped;
  terms.forEach(term => {
    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    result = result.replace(regex, '<strong class="sr-highlight">$1</strong>');
  });
  return result;
}

// ── WEAKNESS DASHBOARD ─────────────────────────────────────────
async function initWeakness() {
  const container = el('weaknessContent');
  container.innerHTML = skeletonBlocks(3);
  try {
    const d = await get(`weakness/${encodeURIComponent(STATE.userId)}`);
    const weak   = d.weak_topics || d.weak || [];
    const allTop = d.all_topics  || d.scores || [];
    const studyPlan = d.study_plan || null;
    const subjectSummary = d.subject_summary || [];
    renderWeakness(container, weak, allTop, studyPlan, subjectSummary);
  } catch(e) {
    container.innerHTML = errorState('Could not load weakness data: ' + e.message);
  }
}

function renderWeakness(container, weak, allTopics, studyPlan, subjectSummary = []) {
  if (!allTopics.length && !weak.length) {
    container.innerHTML = `<div class="empty-state">
      <p>No topic data yet. Complete a quiz first to see your weakness analysis!</p>
      <button class="btn btn-primary btn-sm" onclick="go('quiz')" style="margin-top:12px">Take a Quiz</button>
    </div>`;
    return;
  }

  let html = '';

  // Study plan overview
  if (studyPlan && studyPlan.status === 'needs_work') {
    html += `<div class="eval-card" style="margin-bottom:20px;border-left:4px solid var(--primary)">
      <h4>📚 Study Plan</h4>
      <p style="font-size:13px;color:var(--text-2)">You have <strong>${studyPlan.total_weak}</strong> weak topic(s)${studyPlan.critical_count ? `, <strong style="color:var(--danger)">${studyPlan.critical_count} critical</strong>` : ''}. Focus on these in order:</p>
      <div style="margin-top:8px">
        ${(studyPlan.plan || []).map(p => `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border-light)">
          <span style="background:var(--primary);color:#fff;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700">${p.order}</span>
          <span style="font-weight:600">${esc(p.topic)}</span>
          <span style="font-size:12px;color:var(--text-3)">${Math.round((p.accuracy||0)*100)}% accuracy • ~${p.estimated_sessions} session(s)</span>
        </div>`).join('')}
      </div>
    </div>`;
  }

  // Summary cards
  const total = allTopics.length;
  const strongCount = allTopics.filter(t => t.status === 'strong').length;
  const weakCount   = allTopics.filter(t => t.status === 'weak').length;
  html += `<div class="weakness-summary">
    <div class="ws-card ws-card-green"><div class="ws-num">${strongCount}</div><div class="ws-label">Strong Topics</div></div>
    <div class="ws-card ws-card-blue"><div class="ws-num">${total - strongCount - weakCount}</div><div class="ws-label">Moderate Topics</div></div>
    <div class="ws-card ws-card-red"><div class="ws-num">${weakCount}</div><div class="ws-label">Weak Topics</div></div>
  </div>`;

  if (subjectSummary.length) {
    html += `<h3 class="weakness-section-title">Subject-wise Overview</h3>`;
    html += `<div class="subject-summary-grid">` + subjectSummary
      .sort((a,b) => (a.subject || '').localeCompare(b.subject || ''))
      .map(s => `<div class="subject-summary-card">
        <div class="subject-summary-head">📚 ${esc(s.subject || 'General Studies')}</div>
        <div class="subject-summary-meta">
          <span class="status-weak">Weak: ${s.weak || 0}</span>
          <span class="status-moderate">Moderate: ${s.moderate || 0}</span>
          <span class="status-strong">Strong: ${s.strong || 0}</span>
        </div>
      </div>`)
      .join('') + `</div>`;
  }

  const bySubject = (arr) => {
    const out = {};
    (arr || []).forEach((t) => {
      const s = (t.subject || 'General Studies').trim() || 'General Studies';
      if (!out[s]) out[s] = [];
      out[s].push(t);
    });
    return out;
  };
  const weakBySubject = bySubject(weak);
  const allBySubject = bySubject(allTopics);

  // Weak topics first (grouped by subject)
  if (weak.length) {
    html += `<h3 class="weakness-section-title">⚠️ Topics Needing Attention</h3>`;
    Object.keys(weakBySubject).sort().forEach((subject) => {
      html += `<div class="topic-subject-head">📚 ${esc(subject)}</div>`;
      weakBySubject[subject].forEach(t => {
      const pct = Math.round(t.accuracy * 100);
      const trend = t.trend || {};
      const advice = t.advice || {};
      const trendIcon = trend.direction === 'improving' ? '📈' : trend.direction === 'declining' ? '📉' : '→';
      html += `<div class="topic-card topic-weak">
        <div class="topic-header">
          <span class="topic-name">${esc(t.topic)}</span>
          <span class="topic-trend">${trendIcon} ${trend.direction || 'stable'}</span>
        </div>
        <div class="topic-bar-wrap">
          <div class="topic-bar"><div class="topic-bar-fill bar-weak" style="width:${pct}%"></div></div>
          <span class="topic-pct">${pct}%</span>
        </div>
        <div class="topic-detail">${t.correct}/${t.total} correct</div>
        ${advice.issue ? `<div style="margin-top:8px;padding:10px;background:var(--bg-2);border-radius:8px">
          <div style="font-weight:600;font-size:13px;color:var(--danger)">${esc(advice.issue)}</div>
          <div style="font-size:12px;color:var(--text-3);margin:4px 0">${esc(advice.reason || '')}</div>
          ${advice.trend_note ? `<div style="font-size:12px;margin:4px 0">${esc(advice.trend_note)}</div>` : ''}
          ${advice.improvement ? `<ul style="font-size:12px;color:var(--text-2);margin:6px 0 0 16px;padding:0">
            ${advice.improvement.map(s => `<li style="margin:3px 0">${esc(s)}</li>`).join('')}
          </ul>` : ''}
        </div>` : (t.recommendation ? `<div class="topic-rec">${esc(t.recommendation)}</div>` : '')}
      </div>`;
      });
    });
  }

  // All topics performance
  if (allTopics.length) {
    html += `<h3 class="weakness-section-title">All Topics Performance</h3>`;
    Object.keys(allBySubject).sort().forEach((subject) => {
      html += `<div class="topic-subject-head">📚 ${esc(subject)}</div>`;
      allBySubject[subject].forEach(t => {
      const pct = Math.round(t.accuracy * 100);
      const colorClass = t.status === 'strong' ? 'bar-strong' : t.status === 'moderate' ? 'bar-moderate' : 'bar-weak';
      html += `<div class="topic-card">
        <div class="topic-header">
          <span class="topic-name">${esc(t.topic)}</span>
          <span class="topic-status status-${t.status || 'moderate'}">${t.status || 'moderate'}</span>
        </div>
        <div class="topic-bar-wrap">
          <div class="topic-bar"><div class="topic-bar-fill ${colorClass}" style="width:${pct}%"></div></div>
          <span class="topic-pct">${pct}%</span>
        </div>
        <div class="topic-detail">${t.correct}/${t.total} correct</div>
      </div>`;
      });
    });
  }

  container.innerHTML = html;
}

// ── LIBRARY ───────────────────────────────────────────────────
async function initLibrary() {
  const container = el('libraryContent');
  if (!container) return;
  container.innerHTML = skeletonBlocks(3);

  // Load user's uploaded documents with live status/progress
  let userDocs = [];
  try {
    if (STATE.userId) {
      const ud = await get(`status/user/${encodeURIComponent(STATE.userId)}`);
      userDocs = ud.documents || [];
      console.log('[LIBRARY] Loaded', userDocs.length, 'user documents (with status)');
    }
  } catch(e) { console.error('[LIBRARY] Failed to load documents:', e); }

  // Unified hierarchy for subject -> unit -> topic -> subtopic (collapsed UI)
  let hierarchy = { subjects: [] };
  try {
    hierarchy = await get(`library/hierarchy/${encodeURIComponent(STATE.userId)}`);
    console.log('[LIBRARY] Loaded unified hierarchy subjects:', (hierarchy.subjects || []).length);
  } catch(e) { console.error('[LIBRARY] Failed to load hierarchy:', e); }

  STATE._libraryHierarchy = hierarchy;
  renderLibrary(container, userDocs, hierarchy);

  // Auto-refresh the library list every ~12s while any docs are still processing.
  const hasProcessing = userDocs.some(d => d.status === 'processing' || d.status === 'partially_ready');
  if (!hasProcessing) {
    if (_libraryRefreshTimer) {
      clearTimeout(_libraryRefreshTimer);
      _libraryRefreshTimer = null;
    }
  } else if (!_libraryRefreshTimer && STATE.currentView === 'library') {
    _libraryRefreshTimer = setTimeout(() => {
      _libraryRefreshTimer = null;
      if (STATE.currentView === 'library') {
        initLibrary();
      }
    }, 12000);
  }
}

function renderLibrary(container, userDocs, hierarchy) {
  let html = '';

  // ── Inline Upload Zone (with subject field) ──
  html += `<div class="lib-upload-zone" id="libUploadZone">
    <label class="lib-dropzone" id="libDropzone" for="libFileInput">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="1.75">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
      </svg>
      <div class="lib-dropzone-text">
        <strong>Upload New Document</strong>
        <span>Drag & drop or click to browse — PDF or Excel, up to 20 MB</span>
      </div>
      <input type="file" id="libFileInput" accept=".pdf,.xlsx" multiple hidden />
    </label>
    <div class="lib-upload-subject-row" id="libSubjectRow" style="display:none">
      <span class="lib-upload-subject-label">📁 Add to Subject Folder:</span>
      <input type="text" id="libUploadSubject" placeholder="e.g. Physics, Machine Learning" class="input" style="flex:1;min-width:160px">
    </div>
    <div id="libUploadFeedback" class="lib-upload-fb"></div>
    <div id="libProgressSection" style="display:none" class="lib-progress">
      <div class="progress-track"><div class="progress-fill" id="libProgressFill"></div></div>
      <p class="progress-label" id="libProgressLabel">Uploading…</p>
    </div>
  </div>`;

  // ── User's Documents ──
  html += `<h3 style="font-size:15px;font-weight:600;margin:20px 0 12px">📄 Your Documents</h3>`;
  if (userDocs.length) {
    html += `<div class="library-doc-list">`;
    userDocs.forEach(doc => {
      const name = doc.filename || doc.doc_id;
      const date = doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '';
      const isActive = doc.doc_id === STATE.docId;
      const pct = typeof doc.progress === 'number' ? Math.round(doc.progress) : null;
      const stage = doc.processing_stage || doc.status || '';
      html += `<div class="lib-user-doc ${isActive ? 'lib-doc-active' : ''}">
        <div class="lib-doc-info">
          <span class="lib-doc-name">📑 ${esc(name)}</span>
          ${date ? `<span class="lib-doc-date">${date}</span>` : ''}
          <span class="lib-doc-status status-${doc.status}">
            ${doc.status}
            ${pct !== null && doc.status !== 'ready' ? ` · ${pct}%` : ''}
            ${stage && doc.status !== 'ready' ? ` · ${esc(stage)}` : ''}
          </span>
          ${doc.queue_position !== null && doc.queue_position !== undefined
            ? `<span class="lib-doc-queue"> · Queue #${doc.queue_position} · ETA ${fmt(doc.estimated_wait)} jobs</span>`
            : ''}
        </div>
        <div class="lib-doc-actions">
          ${doc.status === 'ready' ? `
            <button class="btn btn-ghost btn-sm" data-action="view" data-id="${esc(doc.doc_id)}">👁 View</button>
            <button class="btn btn-primary btn-sm" data-action="use" data-id="${esc(doc.doc_id)}" data-name="${esc(name)}">▶ Use</button>
            <button class="btn btn-ghost btn-sm" data-action="open-course" data-id="${esc(doc.doc_id)}" data-name="${esc(name)}">🎓 Open as Course</button>
            <button class="btn btn-ghost btn-sm" data-action="tag" data-id="${esc(doc.doc_id)}" data-name="${esc(name)}">📁 Tag</button>
          ` : `<span style="font-size:12px;color:var(--text-3)">Processing…</span>`}
          <button class="btn btn-ghost btn-sm" style="color:var(--danger)" data-action="delete" data-id="${esc(doc.doc_id)}">🗑</button>
        </div>
      </div>`;
    });
    html += `</div>`;
  } else {
    html += `<div class="empty-state">
      <p>No documents uploaded yet. Upload your first PDF above to get started!</p>
    </div>`;
  }

  // ── Subject Library (unified hierarchical view, collapsed) ──
  const subjects = (hierarchy && hierarchy.subjects) ? hierarchy.subjects : [];
  html += `<div style="display:flex;align-items:center;justify-content:space-between;margin:24px 0 12px">
    <h3 style="font-size:15px;font-weight:600;margin:0">📚 Subject Library</h3>
    <button class="btn btn-ghost btn-sm" data-action="reclassify" id="reclassifyBtn">🔄 Auto-Classify All</button>
  </div>`;
  if (subjects.length) {
    html += `<div class="library-grid">` +
      subjects.map(s => {
        const subj = s.subject || 'General Studies';
        const docCount = (s.documents || []).length;
        return `<div class="lib-subject-card" data-action="toggle-subject-hierarchy" data-subject="${esc(subj)}">
          <div class="lib-subject-icon">📚</div>
          <div class="lib-subject-name">${esc(subj)}</div>
          <div class="lib-subject-count">${docCount} doc${docCount !== 1 ? 's' : ''}</div>
        </div>`;
      }).join('') +
    `</div>
    <div id="libHierarchyPanel" class="lib-docs-panel"></div>`;
  } else {
    html += `<div class="empty-state" style="margin-bottom:16px">
      <p>No hierarchy yet. Upload and process a document to generate Subject → Unit → Topic → Subtopic.</p>
    </div>`;
  }

  container.innerHTML = html;

  // Wire up inline upload events AFTER rendering
  _wireLibraryUpload();
  // Wire up event delegation for ALL library buttons
  _wireLibraryActions(container);
}

function _wireLibraryUpload() {
  const dropzone = el('libDropzone');
  const fileIn   = el('libFileInput');
  if (!dropzone || !fileIn) return;

  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
  dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('drag-over'); });
  dropzone.addEventListener('drop', e => {
    e.preventDefault(); dropzone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;
    if (files.length === 1) {
      _showSubjectRow(files[0]);
    } else {
      // For multi-select in Library, reuse the global multi-upload pipeline.
      uploadFilesMulti(files);
    }
  });
  fileIn.addEventListener('change', e => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    if (files.length === 1) {
      _showSubjectRow(files[0]);
    } else {
      uploadFilesMulti(files);
    }
  });
}

// Show the subject field after file is selected, then start upload
function _showSubjectRow(file) {
  const row = el('libSubjectRow');
  if (row) row.style.display = 'flex';
  // Store the pending file on window so we can start upload
  window._pendingUploadFile = file;
  const fb = el('libUploadFeedback');
  if (fb) { fb.textContent = `Selected: "${file.name}" — enter a subject folder (optional) then uploading will start in 2s…`; fb.className = 'lib-upload-fb'; }
  // Auto-start upload after a short delay so user can type subject
  setTimeout(() => {
    _libUploadFile(window._pendingUploadFile);
    window._pendingUploadFile = null;
  }, 2500);
}

async function _libUploadFile(file) {
  if (!file) return;
  const fb   = el('libUploadFeedback');
  const prog = el('libProgressSection');
  const fill = el('libProgressFill');
  const lbl  = el('libProgressLabel');
  const subjectInput = el('libUploadSubject');
  const subject = subjectInput ? subjectInput.value.trim() : '';

  if (fb) { fb.textContent = `Uploading "${file.name}"…`; fb.className = 'lib-upload-fb'; }
  if (prog) prog.style.display = 'block';
  if (fill) fill.style.width = '20%';
  if (lbl) lbl.textContent = 'Uploading…';

  const fd = new FormData();
  fd.append('file', file);
  fd.append('user_id', STATE.userId || 'guest');

  try {
    const res = await fetch('/api/upload', { method:'POST', body:fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');
    STATE.docId = data.doc_id;
    STATE.docFilename = data.filename || file.name;
    _saveDocState();

    // Auto-tag to subject library if a subject was entered
    if (subject) {
      try {
        await api('library/add', { doc_id: STATE.docId, subject, title: STATE.docFilename });
      } catch(e) { console.warn('Auto-tag failed:', e); }
    }

    if (data.status === 'ready') {
      if (fb) { fb.textContent = '✅ Document ready!' + (subject ? ` Added to "${subject}"` : ''); fb.className = 'lib-upload-fb success'; }
      if (fill) fill.style.width = '100%';
      if (lbl) lbl.textContent = 'Done!';
      setTimeout(() => { if (prog) prog.style.display = 'none'; const sr = el('libSubjectRow'); if (sr) sr.style.display = 'none'; initLibrary(); }, 800);
      fetchScore();
      const sbEl = el('topbarStatus');  if (sbEl) sbEl.textContent = 'READY';
      const fnEl = el('topbarFilename'); if (fnEl) fnEl.textContent = STATE.docFilename;
    } else {
      _libPollStatus(fb, prog, fill, lbl, subject);
    }
  } catch(e) {
    if (fb) { fb.textContent = e.message; fb.className = 'lib-upload-fb error'; }
    if (prog) prog.style.display = 'none';
  }
}

async function _libPollStatus(fb, prog, fill, lbl, subject) {
  if (fill) fill.style.width = '55%';
  if (lbl) lbl.textContent = 'Processing document…';
  try {
    const d = await get(`status/${STATE.docId}`);
    if (d.status === 'ready') {
      // Auto-tag to subject if specified
      if (subject) {
        try { await api('library/add', { doc_id: STATE.docId, subject, title: STATE.docFilename }); } catch(e) {}
      }
      if (fill) fill.style.width = '100%';
      if (lbl) lbl.textContent = 'Done!';
      if (fb) { fb.textContent = '✅ Document processed!' + (subject ? ` Added to "${subject}"` : ''); fb.className = 'lib-upload-fb success'; }
      const sbEl = el('topbarStatus');  if (sbEl) sbEl.textContent = 'READY';
      const fnEl = el('topbarFilename'); if (fnEl) fnEl.textContent = STATE.docFilename;
      fetchScore();
      setTimeout(() => { if (prog) prog.style.display = 'none'; const sr = el('libSubjectRow'); if (sr) sr.style.display = 'none'; initLibrary(); }, 800);
    } else if (d.status === 'failed') {
      throw new Error(d.error || 'Processing failed');
    } else {
      // No fake progress: interpret progress based on `status`.
      let pct = 40;
      if (d.status === 'partially_ready') {
        pct = 70;
      } else if (d.status === 'processing') {
        if (d.processing_stage === 'uploaded' || d.processing_stage === 'parsed') pct = 20;
        else if (d.processing_stage === 'structured' || d.processing_stage === 'embedded') pct = 40;
        else if (d.processing_stage === 'indexed') pct = 70;
      }
      if (fill) fill.style.width = pct + '%';
      if (lbl) lbl.textContent = `Stage: ${d.processing_stage || 'processing'}…`;
      setTimeout(() => _libPollStatus(fb, prog, fill, lbl, subject), 3000);
    }
  } catch(e) {
    if (fb) { fb.textContent = e.message; fb.className = 'lib-upload-fb error'; }
    if (prog) prog.style.display = 'none';
  }
}

// Tag an existing doc with a subject (via prompt)
async function promptTagDoc(docId, docName) {
  console.log('[TAG] promptTagDoc called:', docId, docName);
  const subject = prompt(`Enter a subject folder for "${docName}":\n(e.g. Physics, Python, Machine Learning)`);
  if (!subject || !subject.trim()) return;
  try {
    await api('library/add', { doc_id: docId, subject: subject.trim(), title: docName });
    alert(`✅ "${docName}" added to "${subject.trim()}"!`);
    initLibrary();
  } catch(e) {
    console.error('[TAG] Error:', e);
    alert('Failed to tag: ' + e.message);
  }
}

// ── EVENT DELEGATION for all library buttons ─────────────────────
function _wireLibraryActions(container) {
  // GUARD: only wire once — prevent duplicate listeners on re-render
  if (container._libActionsWired) return;
  container._libActionsWired = true;

  container.addEventListener('click', function(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    const action  = btn.dataset.action;
    const docId   = btn.dataset.id;
    const docName = btn.dataset.name;
    const subject = btn.dataset.subject;
    const nodeId  = btn.dataset.node;

    console.log('[LIB-ACTION]', action, docId, docName, subject);

    if (action === 'view') {
      openPdfViewer(docId);
      return;
    }

    if (action === 'use') {
      activateDoc(docId, docName);
      return;
    }

    if (action === 'open-course') {
      activateDoc(docId, docName);
      openCourseView(docId, docName);
      return;
    }

    if (action === 'open-course-subtopic') {
      activateDoc(docId, docName);
      openCourseView(docId, docName, nodeId || '');
      return;
    }

    if (action === 'tag') {
      var subj = window.prompt('Enter a subject folder for "' + (docName||'') + '":\n(e.g. Physics, Python, Machine Learning)');
      if (!subj || !subj.trim()) return;
      api('library/add', { doc_id: docId, subject: subj.trim(), title: docName })
        .then(function() { window.alert('✅ Added to "' + subj.trim() + '"!'); initLibrary(); })
        .catch(function(err) { console.error('[TAG]', err); window.alert('Failed: ' + err.message); });
      return;
    }

    if (action === 'delete') {
      if (!window.confirm('Delete this document permanently? This cannot be undone.')) return;
      fetch('/api/doc/' + docId, { method: 'DELETE' })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          api('library/remove', { doc_id: docId }).catch(function(){});
          if (STATE.docId === docId) {
            STATE.docId = null; STATE.docFilename = null;
            var fn = el('topbarFilename'); if (fn) fn.textContent = 'No document';
            var sb = el('topbarStatus'); if (sb) sb.textContent = '';
          }
          initLibrary();
        })
        .catch(function(err) { console.error('[DELETE]', err); window.alert('Delete failed: ' + err.message); });
      return;
    }

    if (action === 'remove-from-subject') {
      // No confirm needed — just untags from folder, doesn't delete the file
      btn.disabled = true;
      btn.textContent = '…';
      api('library/remove', { doc_id: docId, subject: subject })
        .then(function() { initLibrary(); })
        .catch(function(err) { console.error('[REMOVE]', err); window.alert('Failed: ' + err.message); btn.disabled = false; btn.textContent = '✕'; });
      return;
    }

    if (action === 'reclassify') {
      btn.disabled = true; btn.textContent = '🔄 Classifying…';
      api('library/reclassify', { user_id: STATE.userId })
        .then(function(res) {
          var results = res.classified || [];
          var classified = results.filter(function(r) { return !r.skipped && !r.error; });
          var skipped = results.filter(function(r) { return r.skipped; });
          window.alert('✅ Done!\n• ' + classified.length + ' classified\n• ' + skipped.length + ' too generic');
          initLibrary();
        })
        .catch(function(err) { console.error('[CLASSIFY]', err); window.alert('Failed: ' + err.message); })
        .finally(function() { btn.disabled = false; btn.textContent = '🔄 Auto-Classify All'; });
      return;
    }

    if (action === 'toggle-subject') {
      _handleToggleSubject(subject, btn.closest('.lib-subject-card'));
      return;
    }

    if (action === 'toggle-subject-hierarchy') {
      _renderSubjectHierarchy(subject);
      return;
    }

    if (action === 'toggle-unit') {
      _toggleHierarchyRow('unit', btn.dataset.doc, nodeId);
      return;
    }
    if (action === 'toggle-topic') {
      _toggleHierarchyRow('topic', btn.dataset.doc, nodeId);
      return;
    }
  });
}

// ----------------------------
// Unified hierarchy panel UI
// ----------------------------
const _HIER = { expandedUnits: new Set(), expandedTopics: new Set(), activeSubject: '' };

function _renderSubjectHierarchy(subjectName) {
  const panel = el('libHierarchyPanel');
  if (!panel) return;
  const hierarchy = STATE._libraryHierarchy || { subjects: [] };
  const subject = (hierarchy.subjects || []).find(s => (s.subject || '') === subjectName);
  _HIER.activeSubject = subjectName || '';

  // highlight selected subject card
  document.querySelectorAll('.lib-subject-card').forEach(c => c.classList.remove('selected'));
  const card = document.querySelector(`.lib-subject-card[data-subject="${CSS.escape(subjectName)}"]`);
  if (card) card.classList.add('selected');

  if (!subject) {
    panel.style.display = 'block';
    panel.innerHTML = `<p style="padding:16px;color:var(--text-3)">No data for "${esc(subjectName)}".</p>`;
    return;
  }

  panel.style.display = 'block';
  panel.innerHTML = (subject.documents || []).map(d => _renderDocHierarchy(d)).join('') ||
    `<p style="padding:16px;color:var(--text-3)">No documents under "${esc(subjectName)}".</p>`;
}

function _renderDocHierarchy(doc) {
  const docId = doc.doc_id;
  const title = doc.title || docId;
  const nodes = doc.nodes || [];
  const byParent = {};
  nodes.forEach(n => {
    const p = n.parent_node_id || '__root__';
    (byParent[p] = byParent[p] || []).push(n);
  });
  const roots = (byParent['__root__'] || []).filter(n => n.level === 'unit');

  return `<div class="lib-doc-row" style="display:block">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
      <span class="lib-doc-title">📑 ${esc(title)}</span>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-ghost btn-sm" data-action="open-course" data-id="${esc(docId)}" data-name="${esc(title)}">🎓 Open as Course</button>
      </div>
    </div>
    <div style="margin-top:10px">
      ${roots.map(u => _renderUnit(docId, title, u, byParent)).join('') || `<div style="color:var(--text-3);font-size:13px">No units found.</div>`}
    </div>
  </div>`;
}

function _renderUnit(docId, docTitle, unit, byParent) {
  const uid = unit.node_id;
  const expanded = _HIER.expandedUnits.has(docId + '::' + uid);
  const topics = (byParent[uid] || []).filter(n => n.level === 'topic');
  return `<div style="margin:8px 0">
    <button class="btn btn-ghost btn-sm" data-action="toggle-unit" data-doc="${esc(docId)}" data-node="${esc(uid)}">
      ${expanded ? '▾' : '▸'} 📁 ${esc(unit.title)}
    </button>
    ${expanded ? `<div style="padding-left:14px;margin-top:6px">
      ${topics.map(t => _renderTopic(docId, docTitle, t, byParent)).join('') || `<div style="color:var(--text-3);font-size:12px">No topics.</div>`}
    </div>` : ``}
  </div>`;
}

function _renderTopic(docId, docTitle, topic, byParent) {
  const tid = topic.node_id;
  const expanded = _HIER.expandedTopics.has(docId + '::' + tid);
  const subs = (byParent[tid] || []).filter(n => n.level === 'subtopic');
  return `<div style="margin:6px 0">
    <button class="btn btn-ghost btn-sm" data-action="toggle-topic" data-doc="${esc(docId)}" data-node="${esc(tid)}">
      ${expanded ? '▾' : '▸'} ${esc(topic.title)}
    </button>
    ${expanded ? `<div style="padding-left:14px;margin-top:6px;display:flex;flex-wrap:wrap;gap:6px">
      ${subs.map(st => `<button class="btn btn-ghost btn-sm" data-action="open-course-subtopic" data-id="${esc(docId)}" data-name="${esc(docTitle)}" data-node="${esc(st.node_id)}">↳ ${esc(st.title)}</button>`).join('')}
    </div>` : ``}
  </div>`;
}

function _toggleHierarchyRow(kind, docId, nodeId) {
  const key = docId + '::' + nodeId;
  if (kind === 'unit') {
    if (_HIER.expandedUnits.has(key)) _HIER.expandedUnits.delete(key);
    else _HIER.expandedUnits.add(key);
  } else {
    if (_HIER.expandedTopics.has(key)) _HIER.expandedTopics.delete(key);
    else _HIER.expandedTopics.add(key);
  }
  // Re-render active subject only
  if (_HIER.activeSubject) _renderSubjectHierarchy(_HIER.activeSubject);
}

// Subject folder expand/collapse
async function _handleToggleSubject(subject, card) {
  console.log('[SUBJECT] toggle:', subject);
  const panel = el('libDocsPanel');
  if (!panel) return;

  if (card.classList.contains('selected')) {
    card.classList.remove('selected');
    panel.innerHTML = '';
    panel.style.display = 'none';
    return;
  }

  document.querySelectorAll('.lib-subject-card').forEach(c => c.classList.remove('selected'));
  card.classList.add('selected');
  panel.style.display = 'block';
  panel.innerHTML = skeletonBlocks(2);

  try {
    const d = await get(`library/${encodeURIComponent(subject)}`);
    const docs = d.documents || d.docs || [];
    if (!docs.length) {
      panel.innerHTML = `<p style="padding:16px;color:var(--text-3)">No documents in "${subject}" yet.</p>`;
      return;
    }
    panel.innerHTML = `<div class="lib-folder-header">
      <h4>📁 ${esc(subject)} — ${docs.length} document${docs.length !== 1 ? 's' : ''}</h4>
    </div>` +
      docs.map(d => {
        const title = d.title || d.doc_id;
        return `<div class="lib-doc-row">
          <span class="lib-doc-title">📑 ${esc(title)}</span>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <button class="btn btn-ghost btn-sm" data-action="view" data-id="${esc(d.doc_id)}">👁 View</button>
            <button class="btn btn-primary btn-sm" data-action="use" data-id="${esc(d.doc_id)}" data-name="${esc(title)}">▶ Use</button>
            <button class="btn btn-ghost btn-sm" data-action="open-course" data-id="${esc(d.doc_id)}" data-name="${esc(title)}">🎓 Open as Course</button>
            <button class="btn btn-ghost btn-sm" data-action="tag" data-id="${esc(d.doc_id)}" data-name="${esc(title)}">📁 Tag</button>
            <button class="btn btn-ghost btn-sm" style="color:var(--danger)" data-action="remove-from-subject" data-id="${esc(d.doc_id)}" data-subject="${esc(subject)}">✕</button>
          </div>
        </div>`;
      }).join('');
  } catch(e) {
    console.error('[SUBJECT] Error:', e);
    panel.innerHTML = `<p style="padding:16px;color:var(--danger)">${e.message}</p>`;
  }
}

async function reclassifyAll() {
  console.log('[CLASSIFY] reclassifyAll called, userId:', STATE.userId);
  const btn = el('reclassifyBtn');
  if (btn) { btn.disabled = true; btn.textContent = '🔄 Classifying…'; }
  try {
    const res = await api('library/reclassify', { user_id: STATE.userId });
    const results = res.classified || [];
    const classified = results.filter(r => !r.skipped && !r.error);
    const skipped = results.filter(r => r.skipped);
    alert(`✅ Done!\n• ${classified.length} document(s) classified into subjects\n• ${skipped.length} too generic to classify`);
    initLibrary();  // Refresh to show new subjects
  } catch(e) {
    console.error('[CLASSIFY] Error:', e);
    alert('Classification failed: ' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🔄 Auto-Classify All'; }
  }
}

async function loadSubjectDocs(subject, card) {
  toggleSubjectDocs(subject, card);
}

async function addToLibrary() {
  if (!STATE.docId) { alert('Upload a document first'); return; }
  const subject = el('librarySubjectInput').value.trim();
  const title   = el('libraryTitleInput').value.trim();
  if (!subject) { alert('Enter a subject name'); return; }
  try {
    await api('library/add', { doc_id: STATE.docId, subject, title });
    el('librarySubjectInput').value = '';
    el('libraryTitleInput').value = '';
    initLibrary();
    alert(`Added to "${subject}" library!`);
  } catch(e) { alert('Failed to add: ' + e.message); }
}

function loadLibraryDoc(docId, title) {
  activateDoc(docId, title);
}

function openCourseView(docId, title, nodeId='', chunkId='', query='', snippet='') {
  const q = new URLSearchParams({
    doc_id: docId || '',
    title: title || docId || 'Course',
  });
  if (nodeId) q.set('node_id', nodeId);
  if (chunkId) q.set('chunk_id', chunkId);
  if (query) q.set('query', query);
  if (snippet) q.set('snippet', snippet);
  window.open(`/course.html?${q.toString()}`, '_blank', 'noopener');
}

// Activate a document as the current working document
function resetRefreshBundle() {
  ['quiz', 'mock_test', 'flashcards', 'summary'].forEach((k) => {
    STATE.refreshBundle[k] = { doc_id: null, source_chunk_ids: [], previous_output: null };
  });
}

function activateDoc(docId, title) {
  if (STATE.docId !== docId) resetRefreshBundle();
  STATE.docId = docId;
  STATE.docFilename = title || docId;
  _saveDocState();
  const fn = el('topbarFilename');
  if (fn) fn.textContent = title || docId;
  const sb = el('topbarStatus');
  if (sb) sb.textContent = 'READY';
  // Refresh library to show active indicator
  initLibrary();
  go('dashboard');
}

// Feature guard — returns true if doc is selected, shows message if not
function requireDoc(containerId) {
  if (STATE.docId) return true;
  const container = el(containerId);
  if (container) {
    container.innerHTML = `<div class="empty-state">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <p style="margin-top:12px;font-weight:600">No document selected</p>
      <p style="font-size:13px;color:var(--text-3)">Please select a document from the Library first.</p>
      <button class="btn btn-primary btn-sm" onclick="go('library')" style="margin-top:12px">📚 Go to Library</button>
    </div>`;
  }
  return false;
}

// ── PDF VIEWER ─────────────────────────────────────────────────
function openPdfViewer(docId) {
  console.log('[VIEW] openPdfViewer called:', docId);
  // Use a programmatic <a> click to bypass popup blockers
  const a = document.createElement('a');
  a.href = `/api/pdf/${docId}`;
  a.target = '_blank';
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function closePdfViewer() {
  const modal = el('pdfModal');
  const frame = el('pdfFrame');
  if (modal) modal.style.display = 'none';
  if (frame) frame.src = '';
}

async function deleteDoc(docId) {
  console.log('[DELETE] deleteDoc called:', docId);
  if (!confirm('Delete this document? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/doc/${docId}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Delete failed');
    // Also remove from library subjects
    try { await api('library/remove', { doc_id: docId }); } catch(e) { /* ok if not in library */ }
    if (STATE.docId === docId) {
      STATE.docId = null;
      STATE.docFilename = null;
      const fn = el('topbarFilename');
      if (fn) fn.textContent = 'No document';
      const sb = el('topbarStatus');
      if (sb) sb.textContent = '';
    }
    initLibrary();
  } catch(e) {
    console.error('[DELETE] Error:', e);
    alert('Delete failed: ' + e.message);
  }
}

// ── EVALUATION ─────────────────────────────────────────────────
function resetEvaluation() {
  const c = el('evaluationContent');
  if (c && !c.innerHTML.trim()) {
    c.innerHTML = `<div class="eval-placeholder">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.25"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      <p>Choose an evaluation to run on your uploaded document.</p>
    </div>`;
  }
}

async function runEvaluation() {
  if (!STATE.docId) { alert('Upload a document first'); return; }
  const btn = el('evalBtn');
  btn.disabled = true; btn.textContent = 'Running…';
  el('evaluationContent').innerHTML = `<div class="eval-running">
    <div class="eval-spinner"></div>
    <p>Running evaluation pipeline… This may take 30–60 seconds.</p>
  </div>`;
  try {
    const d = await api('evaluate/' + STATE.docId, {});
    renderEvalResult(d, 'Evaluation Results');
  } catch(e) {
    el('evaluationContent').innerHTML = errorState('Evaluation failed: ' + e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Run Evaluation';
  }
}

async function runStabilityEval() {
  if (!STATE.docId) { alert('Upload a document first'); return; }
  const btn = el('stableBtn');
  btn.disabled = true; btn.textContent = 'Running 3 runs…';
  el('evaluationContent').innerHTML = `<div class="eval-running">
    <div class="eval-spinner"></div>
    <p>Running stability test (3 runs with data variation)… This may take 2–3 minutes.</p>
  </div>`;
  try {
    const d = await api('evaluate/stable/' + STATE.docId, {});
    const se = d.stability_evaluation || d;
    renderStabilityResult(se);
  } catch(e) {
    el('evaluationContent').innerHTML = errorState('Stability test failed: ' + e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Run Stability Test (3 runs)';
  }
}

async function loadSystemReport() {
  if (!STATE.docId) { alert('Upload a document first'); return; }
  const btn = el('reportBtn');
  btn.disabled = true; btn.textContent = 'Loading…';
  try {
    const d = await get(`system/report/${STATE.docId}`);
    renderSystemReport(d);
  } catch(e) {
    el('evaluationContent').innerHTML = errorState('Report failed: ' + e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Load System Report';
  }
}

function renderEvalResult(d, title) {
  const abl = d.ablation || {};
  const lat = d.latency_ms || {};
  const fail = d.failure_analysis || {};

  let html = `<h3 class="eval-section-title">${title}</h3>`;

  // Ablation table
  html += `<div class="eval-card">
    <h4>Ablation Study — Retrieval Quality</h4>
    <table class="eval-table">
      <thead><tr><th>System</th><th>Recall@5</th><th>MRR</th><th>Not Found Acc</th></tr></thead>
      <tbody>
        <tr><td>Baseline (Vector only)</td><td>${fmt(abl.baseline_recall_at_5)}</td><td>${fmt(abl.baseline_mrr)}</td><td>—</td></tr>
        <tr><td>Hybrid (BM25+FAISS+RRF)</td><td class="${abl.hybrid_recall_at_5 >= abl.baseline_recall_at_5 ? 'eval-better' : ''}">${fmt(abl.hybrid_recall_at_5)}</td><td>${fmt(abl.hybrid_mrr)}</td><td>—</td></tr>
        <tr><td>Reranked</td><td class="${abl.reranked_recall_at_5 >= abl.hybrid_recall_at_5 ? 'eval-better' : ''}">${fmt(abl.reranked_recall_at_5)}</td><td>${fmt(abl.reranked_mrr)}</td><td>${fmt(abl.not_found_accuracy)}</td></tr>
      </tbody>
    </table>
  </div>`;

  // Latency
  if (Object.keys(lat).length) {
    html += `<div class="eval-card">
      <h4>Latency Breakdown</h4>
      <div class="latency-chips">
        ${Object.entries(lat).map(([k,v]) => `<div class="lat-chip"><span class="lat-label">${k}</span><span class="lat-val">${v}ms</span></div>`).join('')}
      </div>
    </div>`;
  }

  // Failure analysis
  if (fail.total_failures !== undefined) {
    html += `<div class="eval-card">
      <h4>Failure Analysis</h4>
      <div class="fail-chips">
        <div class="fail-chip"><span>Total Failures</span><strong>${fail.total_failures}</strong></div>
        ${Object.entries(fail.failure_types || {}).map(([k,v]) => `<div class="fail-chip"><span>${k}</span><strong>${v}</strong></div>`).join('')}
      </div>
    </div>`;
  }

  el('evaluationContent').innerHTML = html;
}

function renderStabilityResult(d) {
  const stable    = d.stability || {};
  const recallObj = d.recall || {};
  const variance  = d.variance || {};
  const variation = d.variation || {};
  const isStable  = stable.passed || false;

  let html = `<div class="eval-card">
    <div class="stability-header">
      <h4>Stability Test Results</h4>
      <span class="stability-badge ${isStable ? 'badge-stable' : 'badge-unstable'}">${isStable ? '\u2713 STABLE' : '\u2717 NOT STABLE'}</span>
    </div>
    <div class="stability-meta">
      <span>Runs: ${d.runs_completed || 3}</span>
      <span>Sampling: ${variation.sampling_ratio ? Math.round(variation.sampling_ratio * 100) + '%' : '80%'} per run</span>
      <span>Data Variation: ${variation.method || 'random sampling'}</span>
    </div>`;

  // Show recall + std table for each system
  if (recallObj.baseline_mean !== undefined || recallObj.hybrid_mean !== undefined) {
    html += `<table class="eval-table" style="margin-top:12px">
      <thead><tr><th>System</th><th>Mean Recall@5</th><th>Std Dev</th><th>Status</th></tr></thead>
      <tbody>
        <tr>
          <td>Baseline</td>
          <td>${fmt(recallObj.baseline_mean)}</td>
          <td>${fmt(variance.baseline_std)}</td>
          <td class="${(variance.baseline_std||0) < 0.05 ? 'eval-better' : 'eval-worse'}">${(variance.baseline_std||0) < 0.05 ? '\u2713 std < 0.05' : '\u2717 std \u2265 0.05'}</td>
        </tr>
        <tr>
          <td>Hybrid</td>
          <td>${fmt(recallObj.hybrid_mean)}</td>
          <td>${fmt(variance.hybrid_std)}</td>
          <td class="${(variance.hybrid_std||0) < 0.05 ? 'eval-better' : 'eval-worse'}">${(variance.hybrid_std||0) < 0.05 ? '\u2713 std < 0.05' : '\u2717 std \u2265 0.05'}</td>
        </tr>
        <tr>
          <td>Reranked</td>
          <td>${fmt(recallObj.reranked_mean)}</td>
          <td>${fmt(variance.reranked_std)}</td>
          <td class="${(variance.reranked_std||0) < 0.05 ? 'eval-better' : 'eval-worse'}">${(variance.reranked_std||0) < 0.05 ? '\u2713 std < 0.05' : '\u2717 std \u2265 0.05'}</td>
        </tr>
      </tbody>
    </table>`;
  }
  html += `</div>`;
  el('evaluationContent').innerHTML = html;
}

function renderSystemReport(d) {
  const status = d.status || 'UNKNOWN';
  const criteria = d.validation_criteria || {};
  const metrics = d.metrics || {};

  let html = `<div class="eval-card">
    <div class="system-report-header">
      <h4>System Validation Report</h4>
      <span class="report-status ${status === 'VALIDATED' ? 'status-validated' : status === 'NEEDS_IMPROVEMENT' ? 'status-needs' : 'status-unknown'}">${status}</span>
    </div>`;

  if (Object.keys(criteria).length) {
    html += `<div class="criteria-list">`;
    Object.entries(criteria).forEach(([key, val]) => {
      const passed = val.passed !== undefined ? val.passed : val;
      const value  = val.value !== undefined ? val.value : '';
      const note   = val.note || '';
      html += `<div class="criterion-row ${passed ? 'crit-pass' : 'crit-fail'}">
        <span class="crit-icon">${passed ? '\u2713' : '\u2717'}</span>
        <span class="crit-name">${key.replace(/_/g,' ')}</span>
        <span class="crit-val">${value}${note ? ' <em style="font-size:11px;opacity:0.7">' + note + '</em>' : ''}</span>
      </div>`;
    });
    html += `</div>`;
  }

  if (metrics.hybrid_recall_at_5 !== undefined) {
    html += `<div style="margin-top:16px">`;
    html += renderEvalMetricRow('Recall@5 (Hybrid)', metrics.hybrid_recall_at_5);
    html += renderEvalMetricRow('MRR (Reranked)', metrics.reranked_mrr);
    html += `</div>`;
  }
  html += `</div>`;
  el('evaluationContent').innerHTML = html;
}

function renderEvalMetricRow(label, val) {
  return `<div style="display:flex;align-items:center;gap:12px;margin:6px 0">
    <span style="width:180px;font-size:13px;color:var(--text-2)">${label}</span>
    <div style="flex:1;background:var(--border-light);border-radius:4px;height:8px">
      <div style="width:${Math.round((val||0)*100)}%;background:var(--primary);height:8px;border-radius:4px"></div>
    </div>
    <span style="font-size:13px;font-weight:600;color:var(--text-1);width:40px;text-align:right">${fmt(val)}</span>
  </div>`;
}

function fmt(v) {
  if (v === undefined || v === null || v === '') return '—';
  if (typeof v === 'number') return v.toFixed ? v.toFixed(3) : v;
  return String(v);
}
