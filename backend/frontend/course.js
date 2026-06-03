const params = new URLSearchParams(window.location.search);
const DOC_ID = params.get("doc_id") || "";
const DOC_TITLE = params.get("title") || "Course";
const START_NODE_ID = params.get("node_id") || "";
const START_CHUNK_ID = params.get("chunk_id") || "";
const USER_ID = localStorage.getItem("intellirag_uid") || "default_user";
const START_HIGHLIGHT_TEXT = params.get("query") || params.get("snippet") || "";
const STATE_KEY = `course_state_${DOC_ID}`;

const COURSE = {
  structure: [],
  nodeContent: {},
  nodeById: new Map(),
  parentById: new Map(),
  selectedNodeId: "",
  expanded: new Set(),
};

function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function loadSavedState() {
  try {
    const raw = localStorage.getItem(STATE_KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    COURSE.selectedNodeId = s.selectedNodeId || "";
    COURSE.expanded = new Set(s.expanded || []);
  } catch (_) {}
}

function saveState() {
  localStorage.setItem(STATE_KEY, JSON.stringify({
    selectedNodeId: COURSE.selectedNodeId,
    expanded: Array.from(COURSE.expanded),
  }));
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
  const src = text.replace(/\r\n/g, "\n");
  const fenceMatches = [];
  let safe = esc(src).replace(/```([\s\S]*?)```/g, (_, code) => {
    const key = `@@FENCE_${fenceMatches.length}@@`;
    fenceMatches.push(`<pre><code>${code.trim()}</code></pre>`);
    return key;
  });

  safe = safe
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>");

  const lines = safe.split("\n");
  let html = "";
  let inUl = false;
  let inOl = false;
  let para = [];

  const flushPara = () => {
    if (!para.length) return;
    html += `<p>${para.join(" ")}</p>`;
    para = [];
  };

  for (const raw of lines) {
    const line = raw.trim();
    const ulMatch = line.match(/^[-*]\s+(.+)/);
    const olMatch = line.match(/^\d+\.\s+(.+)/);

    if (!line) {
      flushPara();
      if (inUl) { html += "</ul>"; inUl = false; }
      if (inOl) { html += "</ol>"; inOl = false; }
      continue;
    }

    if (/^<h[1-3]>/.test(line)) {
      flushPara();
      if (inUl) { html += "</ul>"; inUl = false; }
      if (inOl) { html += "</ol>"; inOl = false; }
      html += line;
      continue;
    }

    if (ulMatch) {
      flushPara();
      if (inOl) { html += "</ol>"; inOl = false; }
      if (!inUl) { html += "<ul>"; inUl = true; }
      html += `<li>${ulMatch[1]}</li>`;
      continue;
    }

    if (olMatch) {
      flushPara();
      if (inUl) { html += "</ul>"; inUl = false; }
      if (!inOl) { html += "<ol>"; inOl = true; }
      html += `<li>${olMatch[1]}</li>`;
      continue;
    }

    if (inUl) { html += "</ul>"; inUl = false; }
    if (inOl) { html += "</ol>"; inOl = false; }
    para.push(line);
  }

  flushPara();
  if (inUl) html += "</ul>";
  if (inOl) html += "</ol>";

  fenceMatches.forEach((block, i) => {
    html = html.replace(`@@FENCE_${i}@@`, block);
  });
  return html;
}

function highlightQueryTerms(text, q) {
  const raw = esc(text || "");
  const query = String(q || "").trim();
  if (!query) return raw;

  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map(t => t.trim())
    .filter(t => t.length > 2);
  if (!terms.length) return raw;

  let out = raw;
  terms.forEach(term => {
    const safe = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`(${safe})`, "ig");
    out = out.replace(re, `<mark class="sr-highlight">$1</mark>`);
  });
  return out;
}

function highlightInHtml(html, q) {
  const query = String(q || "").trim();
  if (!query) return html;
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map(t => t.trim())
    .filter(t => t.length > 2);
  if (!terms.length) return html;

  const root = document.createElement("div");
  root.innerHTML = html;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const escapedTerms = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(${escapedTerms.join("|")})`, "ig");

  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);

  textNodes.forEach((txtNode) => {
    const original = txtNode.nodeValue || "";
    if (!re.test(original)) return;
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    original.replace(re, (m, _g, off) => {
      if (off > last) frag.appendChild(document.createTextNode(original.slice(last, off)));
      const mark = document.createElement("mark");
      mark.className = "sr-highlight";
      mark.textContent = m;
      frag.appendChild(mark);
      last = off + m.length;
      return m;
    });
    if (last < original.length) frag.appendChild(document.createTextNode(original.slice(last)));
    txtNode.parentNode.replaceChild(frag, txtNode);
  });
  return root.innerHTML;
}

function findNode(nodeId) {
  return COURSE.nodeById.get(nodeId) || null;
}

function firstUsableNode() {
  for (const id of COURSE.nodeById.keys()) {
    if ((COURSE.nodeContent[id] || "").trim().length > 0) {
      return COURSE.nodeById.get(id) || null;
    }
  }
  return null;
}

function hydrateNodeIndex(nodes) {
  COURSE.nodeById.clear();
  COURSE.parentById.clear();
  const stack = [...(nodes || [])];
  while (stack.length) {
    const node = stack.pop();
    COURSE.nodeById.set(node.id, node);
    for (const child of (node.children || [])) {
      COURSE.parentById.set(child.id, node.id);
      stack.push(child);
    }
  }
}

function expandAllParents(nodeId) {
  let cur = nodeId;
  while (cur) {
    const parent = COURSE.parentById.get(cur);
    if (!parent) break;
    COURSE.expanded.add(parent);
    cur = parent;
  }
}

function firstContentDescendant(startId) {
  const start = findNode(startId);
  if (!start) return null;
  const stack = [...(start.children || [])];
  while (stack.length) {
    const n = stack.shift();
    if (((COURSE.nodeContent[n.id] || "").trim().length > 0)) return n;
    if (n.children && n.children.length) stack.push(...n.children);
  }
  return null;
}

function expandAllFolders(nodes) {
  const stack = [...(nodes || [])];
  while (stack.length) {
    const n = stack.pop();
    if (n.children && n.children.length) COURSE.expanded.add(n.id);
    for (const ch of (n.children || [])) stack.push(ch);
  }
}

function renderTree() {
  const container = el("courseTree");
  const rows = [];

  function walk(nodes, depth) {
    (nodes || []).forEach(node => {
      const hasChildren = (node.children || []).length > 0;
      const expanded = COURSE.expanded.has(node.id);
      const selected = COURSE.selectedNodeId === node.id ? "selected" : "";
      const indentClass = `tree-indent-${Math.min(depth, 3)}`;
      rows.push(`
        <div class="tree-row ${indentClass} ${selected}" data-id="${node.id}" data-has-children="${hasChildren ? "1" : "0"}" data-toggle="${hasChildren ? "1" : "0"}">
          <span class="tree-toggle">${hasChildren ? (expanded ? "▾" : "▸") : "·"}</span>
          <span>${esc(node.heading)}</span>
        </div>
      `);
      if (hasChildren && expanded) walk(node.children, depth + 1);
    });
  }

  walk(COURSE.structure, 1);
  container.innerHTML = rows.join("") || "<p>No headings detected.</p>";
}

function selectNode(nodeId) {
  const node = findNode(nodeId);
  if (!node) return;

  // If user clicked a folder node (no content), jump to first subtopic with content.
  const content = (COURSE.nodeContent[nodeId] || "").trim();
  if (!content && node.children && node.children.length) {
    // If we're here due to a URL deep-link (search -> course),
    // keep the specified node stable so `chunk_id` can be resolved correctly.
    const isUrlDeepLink = Boolean(START_NODE_ID && START_NODE_ID === nodeId);
    if (!isUrlDeepLink) {
      const childWithContent = firstContentDescendant(nodeId);
      if (childWithContent) {
        expandAllParents(childWithContent.id);
        COURSE.selectedNodeId = childWithContent.id;
        saveState();
        renderTree();
        return selectNode(childWithContent.id);
      }
    }
  }

  COURSE.selectedNodeId = nodeId;
  saveState();
  updateTreeSelection();

  el("sectionTitle").textContent = node.heading || "Section";
  el("sectionContent").innerHTML = renderMd(content || "No section content available.");
}

async function loadChunksAndScroll() {
  if (!START_CHUNK_ID || !COURSE.selectedNodeId) return;

  try {
    const resp = await fetch(
      `/api/node_chunks/${encodeURIComponent(DOC_ID)}/${encodeURIComponent(COURSE.selectedNodeId)}?user_id=${encodeURIComponent(USER_ID)}`
    );
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Failed to load node chunks");

    const chunks = data.chunks || [];
    if (!chunks.length) return;

    // Render chunk list so we can scroll to the exact match.
    el("sectionContent").innerHTML = `
      <div class="sr-chunk-list" style="margin-top:10px">
        ${chunks
          .map((c) => {
            const cid = String(c.chunk_id || "");
            const page = c.page || 1;
            const text = highlightInHtml(renderMd(c.text || ""), START_HIGHLIGHT_TEXT);
            const isTarget = cid === String(START_CHUNK_ID);
            return `
              <div class="sr-chunk" id="chunk-${cid}" data-page="${page}"
                style="padding:10px;border:1px solid var(--border-light);margin:10px 0;background:${isTarget ? "rgba(37,99,235,0.08)" : "transparent"}">
                <div style="font-size:12px;color:var(--text-3);margin-bottom:6px">Page ${page}</div>
                <div class="sr-chunk-text">${text}</div>
              </div>
            `;
          })
          .join("")}
      </div>
    `;

    // Scroll to exact chunk if present, else fallback to first.
    const target = document.getElementById(`chunk-${START_CHUNK_ID}`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      const first = el("sectionContent")?.querySelector(".sr-chunk");
      first?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (e) {
    console.warn("[Course] loadChunksAndScroll failed:", e);
  }
}

function getLlmVariantCourse() {
  return localStorage.getItem("intellirag") === "30b" ? "30b" : "105b";
}

function updateTreeSelection() {
  const active = document.querySelector(".tree-row.selected");
  if (active) active.classList.remove("selected");
  const next = document.querySelector(`.tree-row[data-id="${COURSE.selectedNodeId}"]`);
  if (next) next.classList.add("selected");
}

async function runAction(action) {
  if (!COURSE.selectedNodeId) return;
  const output = el("aiOutput");
  output.style.display = "block";
  output.innerHTML = "Generating...";
  try {
    const res = await fetch("/api/course/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_id: DOC_ID,
        node_id: COURSE.selectedNodeId,
        action,
        llm_variant: getLlmVariantCourse(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Action failed");
    output.innerHTML = `<h3>${action === "summarize" ? "Summary" : "Detailed Explanation"}</h3>${renderMd(data.answer || "")}`;
  } catch (e) {
    output.innerHTML = `<p style="color:#b91c1c">${esc(e.message)}</p>`;
  }
}

function appendMentor(role, text) {
  const box = el("mentorMsgs");
  const d = document.createElement("div");
  d.className = `mentor-msg ${role}`;
  d.innerHTML = renderMd(text);
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

async function sendMentor() {
  const inp = el("mentorInput");
  const q = (inp.value || "").trim();
  if (!q) return;
  inp.value = "";
  appendMentor("user", q);
  appendMentor("ai", "Thinking...");
  const pending = el("mentorMsgs").lastElementChild;
  try {
    const res = await fetch("/api/course/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_id: DOC_ID,
        question: q,
        node_id: COURSE.selectedNodeId || "",
        user_id: USER_ID,
        llm_variant: getLlmVariantCourse(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Chat failed");
    pending.innerHTML = renderMd(data.answer || "");
  } catch (e) {
    pending.innerHTML = `<span style="color:#b91c1c">${esc(e.message)}</span>`;
  }
}

async function init() {
  if (!DOC_ID) {
    el("courseTitle").textContent = "Invalid course link (missing doc_id).";
    return;
  }

  el("courseTitle").textContent = DOC_TITLE || DOC_ID;
  loadSavedState();

  const res = await fetch(`/api/course/${encodeURIComponent(DOC_ID)}/structure`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to load course structure");
  COURSE.nodeContent = data.node_content || {};
  COURSE.structure = data.structure || [];
  hydrateNodeIndex(COURSE.structure);

  if (!COURSE.expanded.size) {
    // Show full hierarchy expanded by default (like earlier behavior).
    expandAllFolders(COURSE.structure);
  }

  let selected = findNode(START_NODE_ID) || findNode(COURSE.selectedNodeId) || firstUsableNode() || (COURSE.structure[0] || null);
  if (selected) {
    // If the selected node has no content, choose nearest descendant with content.
    const hasContent = ((COURSE.nodeContent[selected.id] || "").trim().length > 0);
    const isSearchDeepLink = Boolean(START_CHUNK_ID && START_NODE_ID && selected.id === START_NODE_ID);
    if (!hasContent && !isSearchDeepLink) {
      const desc = firstContentDescendant(selected.id) || firstUsableNode();
      if (desc) selected = desc;
    }
    COURSE.selectedNodeId = selected.id;
    expandAllParents(selected.id);
  }
  renderTree();
  if (COURSE.selectedNodeId) selectNode(COURSE.selectedNodeId);
  // Deep link: open in Course at the exact chunk match.
  await loadChunksAndScroll();

  el("courseTree").addEventListener("click", (e) => {
    const row = e.target.closest(".tree-row");
    if (!row) return;
    const id = row.dataset.id;
    const hasChildren = row.dataset.hasChildren === "1";
    const onToggle = e.target.closest(".tree-toggle");
    if (hasChildren && onToggle) {
      if (COURSE.expanded.has(id)) COURSE.expanded.delete(id);
      else COURSE.expanded.add(id);
      saveState();
      renderTree();
      return;
    }
    if (hasChildren && !COURSE.expanded.has(id)) COURSE.expanded.add(id);
    selectNode(id);
  });

  el("btnSummarize").addEventListener("click", () => runAction("summarize"));
  el("btnExplain").addEventListener("click", () => runAction("explain"));

  el("mentorFab").addEventListener("click", () => {
    const panel = el("mentorPanel");
    panel.style.display = panel.style.display === "none" ? "flex" : "none";
  });
  el("mentorClose").addEventListener("click", () => { el("mentorPanel").style.display = "none"; });
  el("mentorSend").addEventListener("click", sendMentor);
  el("mentorInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMentor(); });
}

init().catch((e) => {
  el("sectionContent").innerHTML = `<p style="color:#b91c1c">${esc(e.message)}</p>`;
});
