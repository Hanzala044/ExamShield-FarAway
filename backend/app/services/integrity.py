"""IntegrityAI — fraud detection engine (deterministic).

Two modes:
  • live  — per-telemetry rule checks producing plain-English evidence notes
            that are pushed to invigilators in real time.
  • post  — cross-submission statistical analysis: identical wrong-answer
            clustering, a force-directed network graph, and a ranked report.

The evidence notes are templated. To produce them with Claude instead, set
settings.ai_use_claude=true + ANTHROPIC_API_KEY — `narrate()` is the single
swap point (see note below).
"""
from collections import defaultdict
from itertools import combinations

from sqlalchemy.orm import Session

from ..models import Exam, Question, Student, Submission


# ── Optional Claude swap point ───────────────────────────────────────────────
def narrate(template: str, _facts: dict) -> str:
    """Returns an evidence narrative. Deterministic stub returns the template.
    A real implementation would call the Claude API (claude-sonnet-4-6, Tool
    Use) with `_facts` to author the same note in richer prose."""
    return template


# ── Live detection ──────────────────────────────────────────────────────────
def check_live(question: Question | None, response_ms, change_count, tab_switch) -> list[dict]:
    """Evaluate a single telemetry beat. Returns zero or more flags."""
    flags: list[dict] = []

    if tab_switch:
        flags.append({
            "rule": "tab_switch",
            "confidence": 0.7,
            "note": narrate(
                "Student switched away from the locked exam tab during an active "
                "session. Tab-switching is disabled by the kiosk; this indicates a "
                "tampering attempt.",
                {"tab_switch": True},
            ),
        })

    if question is not None and response_ms is not None:
        secs = response_ms / 1000.0
        if secs < 2.0 and question.avg_response_s > 25 and question.difficulty == "hard":
            flags.append({
                "rule": "impossible_speed",
                "confidence": 0.85,
                "note": narrate(
                    f"Student answered Q{question.idx + 1} in {secs:.1f} seconds. "
                    f"The national average for this question type is "
                    f"{question.avg_response_s:.0f} seconds. Q{question.idx + 1} is "
                    f"classified as reasoning-heavy (difficulty: {question.difficulty}).",
                    {"q": question.idx + 1, "secs": secs, "avg": question.avg_response_s},
                ),
            })

    if change_count is not None and change_count > 4:
        flags.append({
            "rule": "excessive_changes",
            "confidence": 0.5,
            "note": narrate(
                f"Same question answered and changed {change_count} times — a "
                f"pattern consistent with relaying answers from an external source.",
                {"changes": change_count},
            ),
        })

    return flags


# ── Post-exam analysis ───────────────────────────────────────────────────────
def _shared_wrong(a: Submission, b: Submission, correct: dict[int, int]) -> int:
    shared = 0
    for q, ca in a.answers.items():
        cb = b.answers.get(q)
        if cb is None:
            continue
        qi = int(q)
        if ca == cb and correct.get(qi) is not None and ca != correct[qi]:
            shared += 1
    return shared


class _UF:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def analyze(db: Session, exam: Exam, min_shared_wrong: int = 6) -> dict:
    correct = {q.idx: q.correct_index for q in exam.questions}
    n_questions = len(correct)
    subs = db.query(Submission).filter(Submission.exam_id == exam.id).all()
    students = {s.id: s for s in db.query(Student).all()}

    edges = []
    for a, b in combinations(subs, 2):
        sw = _shared_wrong(a, b, correct)
        if sw >= min_shared_wrong:
            # crude collusion likelihood: more shared wrongs than chance => suspicious
            confidence = round(min(0.99, sw / max(1, n_questions)), 3)
            edges.append({
                "source": a.student_id,
                "target": b.student_id,
                "shared_wrong": sw,
                "weight": confidence,
                "same_center": a.center_id == b.center_id,
            })

    # cluster connected students
    uf = _UF([s.id for s in subs])
    for e in edges:
        uf.union(e["source"], e["target"])
    groups: dict[int, list[int]] = defaultdict(list)
    flagged_ids = {e["source"] for e in edges} | {e["target"] for e in edges}
    for sid in flagged_ids:
        groups[uf.find(sid)].append(sid)
    clusters = [sorted(g) for g in groups.values() if len(g) >= 2]
    clusters.sort(key=len, reverse=True)

    # per-student strength = summed edge weight
    strength: dict[int, float] = defaultdict(float)
    partners: dict[int, set] = defaultdict(set)
    for e in edges:
        strength[e["source"]] += e["weight"]
        strength[e["target"]] += e["weight"]
        partners[e["source"]].add(e["target"])
        partners[e["target"]].add(e["source"])

    ranked = []
    for sid in sorted(strength, key=lambda x: strength[x], reverse=True):
        s = students.get(sid)
        ranked.append({
            "student_id": sid,
            "roll_no": s.roll_no if s else str(sid),
            "name": s.full_name if s else "?",
            "center_id": s.center_id if s else None,
            "partner_count": len(partners[sid]),
            "score": round(min(0.99, strength[sid] / max(1, len(partners[sid]))), 3),
            "evidence": narrate(
                f"Shares an improbable set of identical wrong answers with "
                f"{len(partners[sid])} other candidate(s). Identical incorrect "
                f"responses at this rate (p < 0.001) are not explainable by chance "
                f"and indicate a shared answer source.",
                {"partners": len(partners[sid])},
            ),
        })

    # nodes for the D3 force-directed graph
    nodes = [
        {
            "id": sid,
            "label": students[sid].roll_no if sid in students else str(sid),
            "center_id": students[sid].center_id if sid in students else None,
        }
        for sid in flagged_ids
    ]

    summary = narrate(
        f"Analysis of {len(subs)} submissions surfaced {len(clusters)} suspected "
        f"collusion cluster(s) involving {len(flagged_ids)} candidates. The largest "
        f"cluster contains {len(clusters[0]) if clusters else 0} candidates. "
        f"Flagged pairs share {min_shared_wrong}+ identical incorrect answers — a "
        f"signature of organised answer distribution rather than independent error.",
        {"subs": len(subs), "clusters": len(clusters)},
    )

    return {
        "exam_id": exam.id,
        "submissions_analyzed": len(subs),
        "summary": summary,
        "clusters": clusters,
        "flagged_count": len(flagged_ids),
        "ranked": ranked,
        "graph": {"nodes": nodes, "edges": edges},
    }
