"""Single-source hierarchy service for library + course view."""
from __future__ import annotations

import re
from typing import Optional
from difflib import SequenceMatcher
import threading

from app.database import SessionLocal, CourseNode


def _slug(s: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return x[:60] or "node"


def _mk_node_id(level: str, idx: int, title: str) -> str:
    return f"{level}_{idx:04d}_{_slug(title)}"


_DOC_HIERARCHY_LOCKS: dict[str, threading.Lock] = {}
_DOC_HIERARCHY_LOCKS_GUARD = threading.Lock()


def _get_doc_hierarchy_lock(doc_id: str) -> threading.Lock:
    # Prevent concurrent hierarchy rebuilds for the same doc_id (SQLite UNIQUE collisions).
    with _DOC_HIERARCHY_LOCKS_GUARD:
        lock = _DOC_HIERARCHY_LOCKS.get(doc_id)
        if lock is None:
            lock = threading.Lock()
            _DOC_HIERARCHY_LOCKS[doc_id] = lock
        return lock


def upsert_doc_hierarchy(doc_id: str, normalized: dict, subject: str = "General Studies") -> None:
    """Create unified hierarchy rows for a document (replace existing)."""
    with _get_doc_hierarchy_lock(doc_id):
        sections = normalized.get("sections", [])
        db = SessionLocal()
        try:
            db.query(CourseNode).filter(CourseNode.doc_id == doc_id).delete()
            # Commit early so other connections don't race on rows
            # during concurrent upserts.
            db.commit()
            order = 0
            subject_title = (subject or "General Studies").strip() or "General Studies"
            subject_id = _mk_node_id("subject", 1, subject_title)
            db.add(CourseNode(
                doc_id=doc_id,
                node_id=subject_id,
                parent_node_id=None,
                level="subject",
                title=subject_title,
                content=None,
                page=1,
                sort_order=order,
            ))
            order += 1

            current_unit_id: Optional[str] = None
            current_topic_id: Optional[str] = None
            unit_i = topic_i = sub_i = 0

            for sec in sections:
                lvl = (sec.get("level") or "h3").lower()
                title = (sec.get("heading") or "Untitled").strip()
                content = (sec.get("content") or "").strip()
                page = int(sec.get("page") or 1)

                if lvl == "h1":
                    unit_i += 1
                    current_unit_id = _mk_node_id("unit", unit_i, title)
                    current_topic_id = None
                    db.add(CourseNode(
                        doc_id=doc_id, node_id=current_unit_id, parent_node_id=subject_id,
                        level="unit", title=title, content=None, page=page, sort_order=order
                    ))
                    order += 1
                    if content:
                        topic_i += 1
                        current_topic_id = _mk_node_id("topic", topic_i, f"{title} Overview")
                        db.add(CourseNode(
                            doc_id=doc_id, node_id=current_topic_id, parent_node_id=current_unit_id,
                            level="topic", title=f"{title} Overview", content=None, page=page, sort_order=order
                        ))
                        order += 1
                        sub_i += 1
                        sub_id = _mk_node_id("subtopic", sub_i, f"{title} Details")
                        db.add(CourseNode(
                            doc_id=doc_id, node_id=sub_id, parent_node_id=current_topic_id,
                            level="subtopic", title=f"{title} Details", content=content, page=page, sort_order=order
                        ))
                        order += 1
                    continue

                if lvl == "h2":
                    if not current_unit_id:
                        unit_i += 1
                        current_unit_id = _mk_node_id("unit", unit_i, "General Unit")
                        db.add(CourseNode(
                            doc_id=doc_id, node_id=current_unit_id, parent_node_id=subject_id,
                            level="unit", title="General Unit", content=None, page=page, sort_order=order
                        ))
                        order += 1
                    topic_i += 1
                    current_topic_id = _mk_node_id("topic", topic_i, title)
                    db.add(CourseNode(
                        doc_id=doc_id, node_id=current_topic_id, parent_node_id=current_unit_id,
                        level="topic", title=title, content=None, page=page, sort_order=order
                    ))
                    order += 1
                    if content:
                        sub_i += 1
                        sub_id = _mk_node_id("subtopic", sub_i, f"{title} Details")
                        db.add(CourseNode(
                            doc_id=doc_id, node_id=sub_id, parent_node_id=current_topic_id,
                            level="subtopic", title=f"{title} Details", content=content, page=page, sort_order=order
                        ))
                        order += 1
                    continue

                # h3+ -> subtopic with content
                if not current_unit_id:
                    unit_i += 1
                    current_unit_id = _mk_node_id("unit", unit_i, "General Unit")
                    db.add(CourseNode(
                        doc_id=doc_id, node_id=current_unit_id, parent_node_id=subject_id,
                        level="unit", title="General Unit", content=None, page=page, sort_order=order
                    ))
                    order += 1
                if not current_topic_id:
                    topic_i += 1
                    current_topic_id = _mk_node_id("topic", topic_i, "General Topic")
                    db.add(CourseNode(
                        doc_id=doc_id, node_id=current_topic_id, parent_node_id=current_unit_id,
                        level="topic", title="General Topic", content=None, page=page, sort_order=order
                    ))
                    order += 1

                sub_i += 1
                sub_id = _mk_node_id("subtopic", sub_i, title)
                db.add(CourseNode(
                    doc_id=doc_id, node_id=sub_id, parent_node_id=current_topic_id,
                    level="subtopic", title=title, content=content, page=page, sort_order=order
                ))
                order += 1

            db.commit()
        finally:
            db.close()


def upsert_from_structure(doc_id: str, structure: list[dict], subject: str = "General Studies") -> None:
    """Backfill hierarchy from existing stored tree structure."""
    normalized_sections = []

    def walk(nodes: list[dict]):
        for n in nodes or []:
            lvl = (n.get("level") or "").lower()
            if lvl in ("h1", "h2", "h3"):
                normalized_sections.append({
                    "heading": n.get("heading", "Untitled"),
                    "level": lvl,
                    "content": n.get("content", "") or "",
                    "page": n.get("page", 1),
                })
            walk(n.get("children", []))

    walk(structure or [])
    upsert_doc_hierarchy(doc_id, {"sections": normalized_sections}, subject=subject)


def get_doc_hierarchy(doc_id: str) -> dict:
    """Return nested hierarchy + node_content map for one document."""
    db = SessionLocal()
    try:
        rows = db.query(CourseNode).filter(CourseNode.doc_id == doc_id).order_by(CourseNode.sort_order.asc()).all()
    finally:
        db.close()

    nodes = [{
        "id": r.node_id,
        "heading": r.title,
        "level": r.level,
        "page": r.page or 1,
        "parent_node_id": r.parent_node_id,
        "children": [],
    } for r in rows]
    by_id = {n["id"]: n for n in nodes}
    roots = []
    for n in nodes:
        pid = n.get("parent_node_id")
        if pid and pid in by_id:
            by_id[pid]["children"].append(n)
        else:
            roots.append(n)

    content = {r.node_id: (r.content or "") for r in rows if (r.content or "").strip()}
    return {"doc_id": doc_id, "structure": roots, "node_content": content}


def get_node(doc_id: str, node_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        r = db.query(CourseNode).filter(CourseNode.doc_id == doc_id, CourseNode.node_id == node_id).first()
        if not r:
            return None
        return {
            "node_id": r.node_id,
            "title": r.title,
            "level": r.level,
            "content": r.content or "",
            "page": r.page or 1,
            "parent_node_id": r.parent_node_id,
        }
    finally:
        db.close()


def delete_doc_hierarchy(doc_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(CourseNode).filter(CourseNode.doc_id == doc_id).delete()
        db.commit()
    finally:
        db.close()


def update_subject_title(doc_id: str, subject: str) -> None:
    """Update subject root title after classifier decides final subject."""
    name = _resolve_subject_label(doc_id, (subject or "").strip() or "General Studies")
    db = SessionLocal()
    try:
        row = db.query(CourseNode).filter(CourseNode.doc_id == doc_id, CourseNode.level == "subject").first()
        if row:
            row.title = name
        else:
            db.add(CourseNode(
                doc_id=doc_id, node_id=_mk_node_id("subject", 1, name),
                parent_node_id=None, level="subject", title=name, content=None, page=1, sort_order=0
            ))
        db.commit()
    finally:
        db.close()


def _resolve_subject_label(doc_id: str, subject: str) -> str:
    """Merge near-duplicate subjects across PDFs into one canonical subject."""
    candidate = (subject or "").strip() or "General Studies"
    db = SessionLocal()
    try:
        rows = db.query(CourseNode).filter(CourseNode.level == "subject", CourseNode.doc_id != doc_id).all()
        if not rows:
            return candidate
        best = candidate
        best_score = 0.0
        c = candidate.lower()
        c_tokens = set(re.findall(r"[a-z0-9]+", c))
        for r in rows:
            t = (r.title or "").strip()
            if not t:
                continue
            tl = t.lower()
            seq = SequenceMatcher(None, c, tl).ratio()
            tok = 0.0
            t_tokens = set(re.findall(r"[a-z0-9]+", tl))
            if c_tokens and t_tokens:
                tok = len(c_tokens & t_tokens) / max(1, len(c_tokens | t_tokens))
            score = max(seq, tok)
            if score > best_score:
                best = t
                best_score = score
        return best if best_score >= 0.62 else candidate
    finally:
        db.close()


def get_user_library_hierarchy(doc_ids: list[str]) -> dict:
    """Return subject->unit->topic->subtopic tree across selected docs."""
    if not doc_ids:
        return {"subjects": []}
    db = SessionLocal()
    try:
        rows = db.query(CourseNode).filter(CourseNode.doc_id.in_(doc_ids)).order_by(CourseNode.sort_order.asc()).all()
    finally:
        db.close()

    grouped: dict[str, dict] = {}
    for r in rows:
        if r.level == "subject":
            key = r.title
            if key not in grouped:
                grouped[key] = {"subject": key, "documents": {}}
            grouped[key]["documents"].setdefault(r.doc_id, {"doc_id": r.doc_id, "nodes": []})
        else:
            subject_row = next((x for x in rows if x.doc_id == r.doc_id and x.level == "subject"), None)
            s_key = subject_row.title if subject_row else "General Studies"
            grouped.setdefault(s_key, {"subject": s_key, "documents": {}})
            grouped[s_key]["documents"].setdefault(r.doc_id, {"doc_id": r.doc_id, "nodes": []})
            grouped[s_key]["documents"][r.doc_id]["nodes"].append({
                "node_id": r.node_id,
                "parent_node_id": r.parent_node_id,
                "title": r.title,
                "level": r.level,
                "page": r.page or 1,
                "has_content": bool((r.content or "").strip()),
            })
    out = []
    for subj, payload in grouped.items():
        docs = []
        for doc in payload["documents"].values():
            docs.append(doc)
        out.append({"subject": subj, "documents": docs})
    return {"subjects": out}


def get_doc_breadcrumb_map(doc_id: str) -> dict[str, str]:
    """Map node title -> Subject > Unit > Topic > Subtopic path."""
    db = SessionLocal()
    try:
        rows = db.query(CourseNode).filter(CourseNode.doc_id == doc_id).order_by(CourseNode.sort_order.asc()).all()
    finally:
        db.close()
    by_id = {r.node_id: r for r in rows}
    out: dict[str, str] = {}
    for r in rows:
        if r.level != "subtopic":
            continue
        path = [r.title]
        cur = r
        while cur.parent_node_id and cur.parent_node_id in by_id:
            cur = by_id[cur.parent_node_id]
            path.append(cur.title)
        path.reverse()
        out[r.title] = " > ".join(path)
    return out
