#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Markdown 生成 data/index.json（题库索引）。

用法：
    python3 scripts/build_index.py --scan     # 只读扫描，输出覆盖报告
    python3 scripts/build_index.py --check    # 只校验，有错误 exit 1
    python3 scripts/build_index.py            # 重新生成 data/index.json

Markdown 是唯一真源；本脚本只解析、不改写任何 Markdown，不复制题干。
零依赖，Python 3.11+。规则见 doc/question-bank.md。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = DATA / "volumes.json"
INDEX = DATA / "index.json"

OK, BAD = "✅", "❌"

# 与 doc/question-bank.md §5.5 一致：数学 11 场的考点序列，用于纯数字题号列的兜底
MATH_SESSION_TOPICS = {
    1: ["profit"], 2: ["profit", "distance"], 3: ["distance"], 4: ["distance"],
    5: ["engineering"], 6: ["engineering"], 7: ["cross-ratio", "concentration"],
    8: ["tiered-pricing", "sets"], 9: ["diophantine"], 10: ["diophantine"],
    11: ["linear-programming", "at-least-at-most"],
}

# 卷面 ❌ 但实质正确的题，出处：数学应用题/全书总结.md「69/81（利润 3 算对填错加回）」
SUBSTANTIVE_OK = {"math-applied-profit-03": True}

ERROR_TAGS = [
    "模型选错", "约束遗漏", "倍数搞错", "移项·符号", "算术笔误",
    "书写跳步", "方程设错", "填涂失误",
]


READ_FILES: set[str] = set()


def read(rel: str) -> str:
    READ_FILES.add(rel)
    return (ROOT / rel).read_text(encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def files_of(slug: str, extra: dict[str, list[str]] | None = None) -> list[Path]:
    patterns = {
        "2020-exam": ["2020年管综合真题/answer*.md"],
        "2024-exam": ["2024年管综真题/answer*.md"],
        "2025-english": ["2025年英语二/answer*.md"],
        "formal-logic": ["形式逻辑与综合推理/answer*/answer*.md"],
        "reasoning-2": ["专项训练二-*/answer*/answer*.md"],
        "math-applied": ["数学应用题/answer*/answer*.md"],
    }
    pats = (extra or {}).get(slug) or patterns[slug]
    out: list[Path] = []
    for pat in pats:
        out.extend(ROOT.glob(pat))
    return sorted(out, key=lambda p: (natural_key(p), p.name))


def natural_key(path: Path) -> tuple:
    nums = re.findall(r"\d+", path.stem)
    return tuple(int(n) for n in nums) if nums else (0,)


def session_id(slug: str, path: Path) -> str:
    return f"{slug}-{path.stem.replace('answer', 'a')}"


# ---------------------------------------------------------------- 答案提取

def answers_from_key(path: str) -> dict[int, str]:
    """解析「| 1~5 | D A B B E |」形式的答案速查表。"""
    text = read(path)
    rows = re.findall(r"\|\s*(\d+)\s*~\s*(\d+)\s*\|\s*([A-E](?:\s+[A-E])*)\s*\|", text)
    out: dict[int, str] = {}
    for lo, _hi, seq in rows:
        for i, ch in enumerate(seq.split()):
            out[int(lo) + i] = ch
    return out


def answers_2020() -> dict[int, str]:
    return answers_from_key("2020年管综合真题/答案速查.md")


def answers_2024() -> dict[int, str]:
    return answers_from_key("2024年管综真题/答案速查.md")


def answers_english() -> dict[int, str]:
    text = read("2025年英语二/试卷总结.md")
    # 9 组，顺序固定：完形 1–20（4 组）、阅读 Text1–4（4 组）、Part B（1 组）
    seq = re.findall(r"[：:]\s*\*{0,2}\s*([A-G](?:\s+[A-G]){4})\s*\*{0,2}", text)
    out: dict[int, str] = {}
    for k, grp in enumerate(seq[:9]):
        for i, ch in enumerate(grp.split()):
            out[k * 5 + i + 1] = ch
    return out


def answers_formal() -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    sources = {
        1: "形式逻辑与综合推理/answer1/answer1-1.md",
        2: "形式逻辑与综合推理/answer2/answer2-1.md",
    }
    for paper, f in sources.items():
        m = re.search(r"参考答案\s*([A-E][A-E\s/]*[A-E])", read(f))
        if not m:
            continue
        seq = re.sub(r"[\s/]", "", m.group(1))
        for i, ch in enumerate(seq, 1):
            out[(paper, i)] = ch
    return out


def answers_reasoning() -> dict[int, str]:
    text = read("专项训练二-五大条件类推理题/答案速查.md")
    rows = re.findall(r"\|\s*(\d+)\s*~\s*(\d+)\s*\|\s*([A-E](?:\s+[A-E])*)\s*\|", text)
    out: dict[int, str] = {}
    for lo, _hi, seq in rows:
        for i, ch in enumerate(seq.split()):
            out[int(lo) + i] = ch
    return out


def detect_math_data_sufficiency(cfg: dict) -> set[tuple[str, int]]:
    """题库中带 (1)(2) 两小问的题 = 条件充分性判断题。"""
    text = read("数学应用题/应用题.md")
    out: set[tuple[str, int]] = set()
    parts = re.split(r"^## 【考点(\d+)】(.+)$", text, flags=re.M)
    topics = {t["section"]: t["topic"] for t in cfg["mathTopics"]}
    for i in range(1, len(parts), 3):
        sec = int(parts[i])
        for chunk in re.split(r"(?=^\*\*\d+\.\*\*)", parts[i + 2], flags=re.M):
            m = re.match(r"^\*\*(\d+)\.\*\*", chunk)
            if not m:
                continue
            if re.search(r"[（(]1[）)]", chunk) and re.search(r"[（(]2[）)]", chunk):
                out.add((topics[sec], int(m.group(1))))
    return out


def answers_math(aliases: dict) -> tuple[dict[tuple[str, int], str], list[str]]:
    out: dict[tuple[str, int], str] = {}
    issues: list[str] = []
    table_row = re.compile(
        r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([✅❌][^|]*)\|", re.M
    )
    for path in sorted(ROOT.glob("数学应用题/answer*/answer*.md")):
        m = re.search(r"answer(\d+)", path.parent.name)
        sess_no = int(m.group(1)) if m else 0
        default_topic = MATH_SESSION_TOPICS.get(sess_no, [None])[0]
        for label, _user, correct_cell, _verdict in table_row.findall(read(rel(path))):
            cm = re.match(r"\s*\*{0,2}([A-E])", correct_cell.strip())
            if not cm:
                issues.append(f"{rel(path)}: 正确答案列无法解析「{correct_cell.strip()[:20]}」")
                continue
            lm = re.match(r"^\s*(?:(\S+?)\s+)?(\d+)\s*$", label.strip())
            if not lm:
                issues.append(f"{rel(path)}: 题号列无法解析「{label.strip()}」")
                continue
            alias, num = lm.group(1), int(lm.group(2))
            if alias:
                topic = aliases.get(alias)
                if not topic:
                    issues.append(f"{rel(path)}: 未知考点简称「{alias}」")
                    continue
            else:
                topic = default_topic
                if not topic:
                    issues.append(f"{rel(path)}: 纯数字题号但无默认考点（answer{sess_no}）")
                    continue
            key = (topic, num)
            if key in out and out[key] != cm.group(1):
                issues.append(f"{rel(path)}: {key} 答案冲突 {out[key]} vs {cm.group(1)}")
            out[key] = cm.group(1)
    return out, issues


def parse_scores() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    eng = read("2025年英语二/试卷总结.md")
    for qid, pat in [
        ("2025-english-translation", r"Section III 翻译\s*\|\s*(\d+)\s*\|\s*(\d+)"),
        ("2025-english-writing-a", r"Section IV Part A 邮件写作\s*\|\s*(\d+)\s*\|\s*(\d+)"),
        ("2025-english-writing-b", r"Section IV Part B 图表作文\s*\|\s*(\d+)\s*\|\s*(\d+)"),
    ]:
        m = re.search(pat, eng)
        if m:
            out[qid] = (int(m.group(1)), int(m.group(2)))
    mg = read("2024年管综真题/批改总结.md")
    for qid, pat in [
        ("2024-exam-essay1", r"论证有效性分析\s*\|\s*估分\s*\|\s*(\d+)\s*\|\s*(\d+)"),
        ("2024-exam-essay2", r"论说文\s*\|\s*估分\s*\|\s*(\d+)\s*\|\s*(\d+)"),
    ]:
        m = re.search(pat, mg)
        if m:
            out[qid] = (int(m.group(1)), int(m.group(2)))
    cn = read("2020年管综合真题/批改总结.md")
    for qid, pat in [
        ("2020-exam-essay1", r"论证有效性分析\s*\|\s*估分\s*\|\s*(\d+)\s*\|\s*(\d+)"),
        ("2020-exam-essay2", r"论说文\s*\|\s*估分\s*\|\s*(\d+)\s*\|\s*(\d+)"),
    ]:
        m = re.search(pat, cn)
        if m:
            out[qid] = (int(m.group(1)), int(m.group(2)))
    return out


# ---------------------------------------------------------------- ID 规则

def qid_2020(n: int) -> str:
    return f"2020-exam-q{n:03d}"


def qid_2024(n: int) -> str:
    return f"2024-exam-q{n:03d}"


def qid_english(n: int) -> str:
    return f"2025-english-q{n:03d}"


def qid_formal(paper: int, n: int) -> str:
    return f"formal-logic-p{paper}-q{n:02d}"


def qid_reasoning(n: int) -> str:
    return f"reasoning-2-q{n:02d}"


def qid_math(topic: str, n: int) -> str:
    return f"math-applied-{topic}-{n:02d}"


# ---------------------------------------------------------------- questions

def build_questions(cfg: dict) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    qs: list[dict] = []
    aliases = cfg["topicAliases"]

    def add(**kw):
        base = dict(
            answer=None, answerSource=None, answerStatus="confirmed", scorable=True,
            revision=None, notes=None,
        )
        base.update(kw)
        qs.append(base)

    a20 = answers_2020()
    for n in range(1, 56):
        if n <= 15:
            section, topic, qtype = "一、问题求解", "问题求解", "problem"
        elif n <= 25:
            section, topic, qtype = "二、条件充分性判断", "条件充分性判断", "data-sufficiency"
        else:
            section, topic, qtype = "三、逻辑推理", "逻辑推理", "logic"
        add(id=qid_2020(n), volume="2020-exam", paper="2020年管综合真题/paper.md",
            number=n, section=section, topic=topic, type=qtype,
            answer=a20.get(n), answerSource="2020年管综合真题/答案速查.md",
            source=f"2020年管综合真题/paper.md#{qid_2020(n)}")
    for suffix, n, qtype, name in [
        ("essay1", 56, "essay", "论证有效性分析"), ("essay2", 57, "writing", "论说文")
    ]:
        add(id=f"2020-exam-{suffix}", volume="2020-exam", paper="2020年管综合真题/paper.md",
            number=n, section="四、写作", topic=name, type=qtype,
            answerStatus="estimated", scorable=False,
            source=f"2020年管综合真题/paper.md#2020-exam-{suffix}")

    a24 = answers_2024()
    for n in range(1, 56):
        if n <= 15:
            section, topic, qtype = "一、问题求解", "问题求解", "problem"
        elif n <= 25:
            section, topic, qtype = "二、条件充分性判断", "条件充分性判断", "data-sufficiency"
        else:
            section, topic, qtype = "三、逻辑推理", "逻辑推理", "logic"
        rev = None
        if n == 25:
            rev = {"date": "2026-11-07", "change": "条件(2) S6=26 → S9=26；正确答案 C → E",
                   "note": "更正前的批改结论基于旧题干"}
        add(id=qid_2024(n), volume="2024-exam", paper="2024年管综真题/paper.md",
            number=n, section=section, topic=topic, type=qtype,
            answer=a24.get(n), answerSource="2024年管综真题/答案速查.md",
            source=f"2024年管综真题/paper.md#{qid_2024(n)}", revision=rev)
    for suffix, n, qtype, name in [
        ("essay1", 56, "essay", "论证有效性分析"), ("essay2", 57, "writing", "论说文")
    ]:
        add(id=f"2024-exam-{suffix}", volume="2024-exam", paper="2024年管综真题/paper.md",
            number=n, section="四、写作", topic=name, type=qtype,
            answerStatus="estimated", scorable=False,
            source=f"2024年管综真题/paper.md#2024-exam-{suffix}")

    aen = answers_english()
    for n in range(1, 46):
        if n <= 20:
            section, topic, qtype = "Section I 完形填空", "完形填空", "cloze"
        elif n <= 40:
            section, topic, qtype = "Section II Part A 阅读", "阅读理解", "reading"
        else:
            section, topic, qtype = "Section II Part B", "小标题匹配", "new-type"
        add(id=qid_english(n), volume="2025-english", paper="2025年英语二/paper.md",
            number=n, section=section, topic=topic, type=qtype,
            answer=aen.get(n), answerSource="2025年英语二/试卷总结.md",
            source=f"2025年英语二/paper.md#{qid_english(n)}")
    for qid, n, qtype, name in [
        ("2025-english-translation", 46, "translation", "翻译"),
        ("2025-english-writing-a", 47, "writing", "写作 Part A"),
        ("2025-english-writing-b", 48, "writing", "写作 Part B"),
    ]:
        add(id=qid, volume="2025-english", paper="2025年英语二/paper.md",
            number=n, section="Section III/IV 主观题", topic=name, type=qtype,
            answerStatus="estimated", scorable=False,
            source="2025年英语二/paper.md#" + qid)

    afm = answers_formal()
    overrides = next(v for v in cfg["volumes"] if v["slug"] == "formal-logic").get("answerOverrides", {})
    for paper in (1, 2):
        src = "形式逻辑与综合推理/形式逻辑与综合推理%s.md" % ("一" if paper == 1 else "二")
        asrc = f"形式逻辑与综合推理/answer{paper}/answer{paper}-1.md"
        for n in range(1, 16):
            qid = qid_formal(paper, n)
            raw = afm.get((paper, n))
            ans = overrides.get(qid, raw)
            add(id=qid, volume="formal-logic", paper=src,
                number=n, section=f"专项训练 1.{paper}", topic="形式逻辑与综合推理",
                type="logic", answer=ans,
                answerSource=(asrc + f"（{qid} 订正 {raw}→{ans}，见 answerOverrides）"
                              if qid in overrides else asrc),
                source=f"{src}#{qid}")

    ar2 = answers_reasoning()
    for n in range(1, 31):
        add(id=qid_reasoning(n), volume="reasoning-2",
            paper="专项训练二-五大条件类推理题/paper.md", number=n,
            section="专项训练 2 五大条件类推理题", topic="条件类推理", type="logic",
            answer=ar2.get(n),
            answerSource="专项训练二-五大条件类推理题/答案速查.md",
            source=f"专项训练二-五大条件类推理题/paper.md#{qid_reasoning(n)}",
            revision=({"date": "2026-11-05", "change": "条件(3) 补回「不售卖杨桃」的「不」字；「不选择丁」改「不选择壬」"}
                      if n == 4 else None))

    am, issues = answers_math(aliases)
    errors.extend(issues)
    ds = detect_math_data_sufficiency(cfg)
    for t in cfg["mathTopics"]:
        for n in range(1, t["count"] + 1):
            key = (t["topic"], n)
            add(id=qid_math(*key), volume="math-applied", paper="数学应用题/应用题.md",
                number=n, section=f"考点{t['section']} {t['name']}", topic=t["name"],
                type="data-sufficiency" if key in ds else "problem",
                answer=am.get(key), answerSource="数学应用题/answer*/answer*.md 判定表",
                source=f"数学应用题/应用题.md#{qid_math(t['topic'], n)}")

    # 跨卷错题重练卷：题目 ID 独立，题干在卷内 paper.md，答案取卷内答案速查
    for vol in cfg["volumes"]:
        if not vol.get("redoQuestions"):
            continue
        slug = vol["slug"]
        ans = answers_from_key(vol["answerSources"][0])
        if len(vol["redoQuestions"]) != vol["totalQuestions"]:
            errors.append(f"{slug}: redoQuestions 条数 ≠ totalQuestions")
        for meta in vol["redoQuestions"]:
            n = meta["number"]
            add(id=f"{slug}-q{n:02d}", volume=slug, paper=vol["papers"][0],
                number=n, section="错题重练", topic=meta["topic"], type=meta["type"],
                answer=ans.get(n), answerSource=vol["answerSources"][0],
                source=f"{vol['papers'][0]}#{slug}-q{n:02d}",
                notes=f"原题 {meta['origin']}")
    return qs, errors


# ---------------------------------------------------------------- sessions

def parse_front_matter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    out: dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def parse_duration(value: str | None) -> float | None:
    if not value or value.lower() in ("null", "~", "-"):
        return None
    m = re.search(r"([\d.]+)\s*min", value, re.I)
    return float(m.group(1)) if m else None


def build_sessions(cfg: dict) -> list[dict]:
    out: list[dict] = []
    extra = {v["slug"]: v["answerGlobs"] for v in cfg["volumes"] if v.get("answerGlobs")}
    for vol in cfg["volumes"]:
        slug = vol["slug"]
        for path in files_of(slug, extra):
            fm = parse_front_matter(read(rel(path)))
            date = (fm.get("time") or "")[:10]
            dur = parse_duration(fm.get("duration"))
            mode = fm.get("timingMode") or ("session" if dur is not None else "none")
            out.append({
                "id": session_id(slug, path),
                "date": date,
                "file": rel(path),
                "volume": slug,
                "questionCount": 0,  # 由 build_attempts 回填
                "timingMode": mode,
                "durationMin": dur,
                "durationSource": "draft" if dur is not None else None,
                "note": None,
            })
    return out


# ---------------------------------------------------------------- attempts

TABLE_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([✅❌][^|]*)\|", re.M
)


def verdict(cell: str):
    if OK in cell:
        return True
    if BAD in cell:
        return False
    return None


def first_letter(cell: str) -> str | None:
    m = re.search(r"(?<![A-Za-z])([A-G])(?![A-Za-z])", cell)
    return m.group(1) if m else None


def last_letter(cell: str) -> str | None:
    found = re.findall(r"(?<![A-Za-z])([A-G])(?![A-Za-z])", cell)
    return found[-1] if found else None


def make_attempt(sess: dict, qid: str, ua, ca, correct, source, note=None) -> dict:
    q_real = correct is not None
    return {
        "id": f"{sess['date']}-{sess['id']}-{qid}",
        "date": sess["date"],
        "sessionId": sess["id"],
        "session": sess["file"],
        "questionId": qid,
        "userAnswer": ua,
        "correctAnswer": ca,
        "correct": correct,
        "substantiveCorrect": (True if qid in SUBSTANTIVE_OK else correct),
        "score": None, "scoreMax": None, "scoreBasis": None,
        "errorTags": [], "errorNote": None,
        "isRedo": False,
        "durationMin": None, "durationSource": None,
        "source": source,
        "verified": q_real,
        "note": note,
    }


def attempts_2024(sess: dict, qmap: dict, qid_fn=qid_2024) -> list[dict]:
    text = read(sess["file"])
    out: list[dict] = []
    for block in re.split(r"(?=^## Q\d+)", text, flags=re.M):
        m = re.match(r"^## Q(\d+)(?:\s*[~～]\s*(\d+))?", block)
        if not m:
            continue
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        head = block.splitlines()[0]
        head_verdict = verdict(head)
        found: dict[int, tuple[str | None, bool | None, str]] = {}
        # 兼容 ### Answer : X ✅ 与 ## Answer : X ✅（answer3.md Q40 用了二级标题）
        for am in re.finditer(r"^#{2,3}\s*[Aa]nswer\s*(?:(\d+)\s*)?[:：]\s*(.*)$", block, re.M):
            q = int(am.group(1)) if am.group(1) else lo
            rest = am.group(2)
            ua = first_letter(rest)
            sig = verdict(rest)
            if sig is None:
                sig = head_verdict
            found[q] = (ua, sig, am.group(0).strip())
        for q in range(lo, hi + 1):
            qid = qid_fn(q)
            ua, sig, src = found.get(q, (None, head_verdict, "无 Answer 行"))
            ca = qmap.get(qid, {}).get("answer")
            note = None if ua else ("未作答（按错计）" if sig is False
                                   else "未作答 / 无判定记录")
            out.append(make_attempt(sess, qid, ua, ca, sig,
                                    f"{sess['file']} {src}", note))
    return out


def attempts_english(sess: dict, qmap: dict) -> list[dict]:
    text = read(sess["file"])
    out: list[dict] = []
    patterns = [
        r"^(\d+)\..*?【([A-G])】\s*([✅❌])",
        r"^(\d+)\..*?\[([A-G])\]\s*([✅❌])",
        r"^### Q(\d+):\s*([A-G])\s*([✅❌])",
    ]
    seen: set[int] = set()
    for line in text.splitlines():
        for pat in patterns:
            m = re.search(pat, line)
            if not m:
                continue
            q, ua, sig = int(m.group(1)), m.group(2), verdict(m.group(3))
            if q in seen:
                break
            seen.add(q)
            qid = qid_english(q)
            out.append(make_attempt(sess, qid, ua, qmap.get(qid, {}).get("answer"),
                                    sig, f"{sess['file']} 逐题行 {line.strip()[:40]}"))
            break
    return out


def attempts_table(sess: dict, qmap: dict, slug: str, aliases: dict) -> tuple[list[dict], list[str]]:
    text = read(sess["file"])
    out: list[dict] = []
    issues: list[str] = []
    sess_no = int(re.search(r"answer(\d+)", sess["file"]).group(1)) if re.search(r"answer(\d+)", sess["file"]) else 0
    default_topic = MATH_SESSION_TOPICS.get(sess_no, [None])[0]
    for label, user_cell, correct_cell, verdict_cell in TABLE_ROW.findall(text):
        lm = re.match(r"^\s*(?:(\S+?)\s+)?(\d+)\s*$", label.strip())
        if not lm:
            issues.append(f"{sess['file']}: 题号列无法解析「{label.strip()}」")
            continue
        alias, num = lm.group(1), int(lm.group(2))
        if slug == "math-applied":
            topic = aliases.get(alias) if alias else default_topic
            if not topic:
                issues.append(f"{sess['file']}: 无法定位考点「{label.strip()}」")
                continue
            qid = qid_math(topic, num)
        elif slug == "formal-logic":
            paper = 1 if "/answer1/" in sess["file"] else 2
            qid = qid_formal(paper, num)
        elif slug.startswith("redo-"):
            qid = f"{slug}-q{num:02d}"
        else:
            qid = qid_reasoning(num)
        ca = first_letter(correct_cell.strip()) or qmap.get(qid, {}).get("answer")
        ua = last_letter(user_cell.strip())
        out.append(make_attempt(sess, qid, ua, ca, verdict(verdict_cell),
                                f"{sess['file']} 判定表 {label.strip()}",
                                None if ua else "未作答"))
    return out, issues


def add_subjective(sessions: list[dict], attempts: list[dict], scores: dict, qmap: dict):
    """主观题：correct=null，估分从总结文件解析，不编造。"""
    targets = {
        "2025-english-translation": ("2025-english", "a5"),
        "2025-english-writing-a": ("2025-english", "a5"),
        "2025-english-writing-b": ("2025-english", "a5"),
        "2024-exam-essay1": ("2024-exam", "a10"),
        "2024-exam-essay2": ("2024-exam", "a11"),
        "2020-exam-essay1": ("2020-exam", "a4"),
        "2020-exam-essay2": ("2020-exam", "a4"),
    }
    for qid, (slug, sid) in targets.items():
        sess = next((s for s in sessions if s["id"] == f"{slug}-{sid}"), None)
        if not sess or qid not in qmap:
            continue
        a = make_attempt(sess, qid, None, None, None,
                         f"{sess['file']} 原文与批改", "主观题：无客观判定，估分见总结")
        if qid in scores:
            a["score"], a["scoreMax"] = scores[qid]
            a["scoreBasis"] = "estimated"
        attempts.append(a)


def parse_redo(qmap: dict, aliases: dict) -> tuple[list[dict], list[str]]:
    text = read("数学应用题/待重做.md")
    rows = re.findall(r"^\|\s*answer(\d+)\s*\|\s*(\S+)\s+(\d+)\s*\|\s*([^|]+?)\s*\|", text, re.M)
    out: list[dict] = []
    issues: list[str] = []
    for sess_no, alias, num, reason in rows:
        topic = aliases.get(alias)
        if not topic:
            issues.append(f"待重做: 未知简称「{alias}」")
            continue
        qid = qid_math(topic, int(num))
        if qid not in qmap:
            issues.append(f"待重做: 悬空 ID {qid}")
            continue
        note = reason.strip()
        out.append({
            "session": f"math-applied-a{sess_no}",
            "questionId": qid,
            "label": f"answer{sess_no} {alias} {num}",
            "errorTags": [t for t in ERROR_TAGS if t in note],
            "errorNote": note,
        })
    return out, issues


def attach_redo(attempts: list[dict], redo: list[dict]):
    for r in redo:
        hit = next((a for a in attempts
                    if a["questionId"] == r["questionId"] and a["sessionId"] == r["session"]), None)
        if hit:
            hit["errorTags"] = r["errorTags"]
            hit["errorNote"] = r["errorNote"]


def build_attempts(sessions: list[dict], qmap: dict, cfg: dict,
                   scores: dict) -> tuple[list[dict], list[dict], list[str], list[str]]:
    aliases = cfg["topicAliases"]
    attempts: list[dict] = []
    redo, issues = parse_redo(qmap, aliases)
    exceptions: list[str] = []
    for sess in sessions:
        slug = sess["volume"]
        if slug in ("2020-exam", "2024-exam"):
            batch = attempts_2024(sess, qmap, qid_2020 if slug == "2020-exam" else qid_2024)
        elif slug == "2025-english":
            batch = attempts_english(sess, qmap)
        else:
            batch, extra = attempts_table(sess, qmap, slug, aliases)
            issues.extend(extra)
        sess["questionCount"] = len(batch)
        attempts.extend(batch)
        for a in batch:
            if a["correct"] is None:
                exceptions.append(f"{a['sessionId']} {a['questionId']}: {a['note'] or '未判定'}")
    add_subjective(sessions, attempts, scores, qmap)
    for a in attempts:
        if a["sessionId"].startswith("redo-"):
            a["isRedo"] = True
    attach_redo(attempts, redo)
    return attempts, redo, issues, exceptions


# ---------------------------------------------------------------- 校验 & 报告

def check_source_numbers(cfg: dict) -> list[str]:
    """校验对象是题库原文：题号连续、无重复、无遗漏，而不是索引内部自洽。"""
    errors: list[str] = []

    def check(label: str, path: str, pattern: str, expected: int):
        nums = [int(x) for x in re.findall(pattern, read(path), re.M)]
        if nums != list(range(1, expected + 1)):
            errors.append(f"{label}: 题号应为 1–{expected}，实际抓到 {len(nums)} 个 {nums[:6]}…")
        return nums

    check("2020-exam", "2020年管综合真题/paper.md", r"^\*\*(\d+)\.\*\*", 57)
    check("2024-exam", "2024年管综真题/paper.md", r"^\*\*(\d+)\.\*\*", 57)
    check("formal-logic 卷一", "形式逻辑与综合推理/形式逻辑与综合推理一.md", r"^\*\*(\d+)\.\*\*", 15)
    check("formal-logic 卷二", "形式逻辑与综合推理/形式逻辑与综合推理二.md", r"^\*\*(\d+)\.\*\*", 15)
    check("reasoning-2", "专项训练二-五大条件类推理题/paper.md", r"^(\d+)\.\s", 30)

    text = read("数学应用题/应用题.md")
    parts = re.split(r"^## 【考点(\d+)】(.+)$", text, flags=re.M)
    for i in range(1, len(parts), 3):
        sec = int(parts[i])
        nums = [int(x) for x in re.findall(r"^\*\*(\d+)\.\*\*", parts[i + 2], re.M)]
        expected = cfg["mathTopics"][sec - 1]["count"]
        if nums != list(range(1, expected + 1)):
            errors.append(f"数学考点{sec}: 题号应为 1–{expected}，实际 {nums}")
    # 英语题号混在文章正文里，逐题行格式分散，暂按 paper.md 的完形 1–20 校验
    eng = [int(x) for x in re.findall(r"^(\d+)\.\s+A\.", read("2025年英语二/paper.md"), re.M)]
    if eng != list(range(1, 21)):
        errors.append(f"英语完形: 题号应为 1–20，实际 {eng}")
    for vol in cfg["volumes"]:
        if vol.get("redoQuestions"):
            check(vol["slug"], vol["papers"][0], r"^\*\*(\d+)\.\*\*", vol["totalQuestions"])
    return errors


def check_anchors(questions: list[dict]) -> list[str]:
    """校验 source 里的锚点在题库 Markdown 中真实存在，防止回链又变成伪锚点。"""
    by_file: dict[str, set[str]] = {}
    for q in questions:
        path, _, frag = q["source"].partition("#")
        if frag:
            by_file.setdefault(path, set()).add(frag)
    errors: list[str] = []
    for path, ids in sorted(by_file.items()):
        found = set(re.findall(r'<a id="([^"]+)"></a>', read(path)))
        missing = ids - found
        if missing:
            errors.append(f"{path}: 缺 {len(missing)} 个 ID 锚点，例 {sorted(missing)[:3]}")
    return errors


def validate(cfg: dict, questions: list[dict], sessions: list[dict],
             attempts: list[dict], redo: list[dict], parse_issues: list[str]) -> list[str]:
    errors = list(parse_issues)
    errors.extend(check_source_numbers(cfg))
    errors.extend(check_anchors(questions))
    qmap = {q["id"]: q for q in questions}
    if len(qmap) != len(questions):
        errors.append("questions.ID 有重复")
    expected_total = sum(v["totalQuestions"] for v in cfg["volumes"])
    expected_scorable = sum(v["scorableQuestions"] for v in cfg["volumes"])
    if len(questions) != expected_total:
        errors.append(f"questions 应为 {expected_total}，实际 {len(questions)}")
    scorable = sum(1 for q in questions if q["scorable"])
    if scorable != expected_scorable:
        errors.append(f"可评分题应为 {expected_scorable}，实际 {scorable}")
    for vol in cfg["volumes"]:
        n = sum(1 for q in questions if q["volume"] == vol["slug"])
        if n != vol["totalQuestions"]:
            errors.append(f"{vol['slug']} 题数应为 {vol['totalQuestions']}，实际 {n}")
    for q in questions:
        if q["scorable"] and not q["answer"]:
            errors.append(f"{q['id']} 缺答案")
        if q["scorable"] and not q["answerSource"]:
            errors.append(f"{q['id']} 缺 answerSource")
        if not q["source"]:
            errors.append(f"{q['id']} 缺 source 回指")
    ids = set(qmap)
    for a in attempts:
        if a["questionId"] not in ids:
            errors.append(f"attempt 悬空引用 {a['questionId']}")
            continue
        if a["correctAnswer"] and qmap[a["questionId"]]["answer"] and \
                a["correctAnswer"] != qmap[a["questionId"]]["answer"]:
            errors.append(f"{a['questionId']} 判定表答案 {a['correctAnswer']} ≠ 题库 {qmap[a['questionId']]['answer']}")
        if a["correct"] is True and a["userAnswer"] != a["correctAnswer"]:
            errors.append(f"{a['questionId']} 判 ✅ 但用户答案 {a['userAnswer']} ≠ 正确答案 {a['correctAnswer']}")
        if a["correct"] is False and a["userAnswer"] == a["correctAnswer"]:
            errors.append(f"{a['questionId']} 判 ❌ 但答案一致")
    if len({a["id"] for a in attempts}) != len(attempts):
        errors.append("attempt.id 有重复")
    if len(redo) != 12:
        errors.append(f"待重做应 12 行，实际映射 {len(redo)}")
    for s in sessions:
        if s["timingMode"] == "none" and s["durationMin"] is not None:
            errors.append(f"{s['id']} timingMode=none 却有时长")
        if s["durationMin"] is not None and not s["durationSource"]:
            errors.append(f"{s['id']} 有时长但缺 durationSource")
    return errors


def report(cfg: dict, questions: list[dict], sessions: list[dict], attempts: list[dict],
           redo: list[dict], errors: list[str], exceptions: list[str]) -> str:
    timing: dict[str, int] = {}
    for s in sessions:
        timing[s["timingMode"]] = timing.get(s["timingMode"], 0) + 1
    scorable = sum(1 for q in questions if q["scorable"])
    answered = sum(1 for q in questions if q["scorable"] and q["answer"])
    judged = sum(1 for a in attempts if a["correct"] is not None)
    lines = [
        f"volumes: {len(cfg['volumes'])}",
        f"questions: {len(questions)} (scorable {scorable}, 有答案 {answered})",
        f"sessions: {len(sessions)} | attempts: {len(attempts)} (有判定 {judged}, 未判定 {len(attempts) - judged})",
        "timing: " + " / ".join(f"{k} {v}" for k, v in sorted(timing.items())),
        f"redo rows: {len(redo)}/12 mapped",
        f"anchors: {sum(1 for q in questions if '#' in q['source'])}/{len(questions)} verified",
        f"answer overrides: {sum(len(v.get('answerOverrides', {})) for v in cfg['volumes'])}（volumes.json 显式订正，原文保留）",
    ]
    for vol in cfg["volumes"]:
        n = sum(1 for q in questions if q["volume"] == vol["slug"])
        na = sum(1 for a in attempts if a["sessionId"].startswith(vol["slug"] + "-"))
        lines.append(f"  {vol['slug']:16s} questions {n:3d}/{vol['totalQuestions']:<3d} attempts {na}")
    if exceptions:
        lines.append(f"known exceptions ({len(exceptions)}): " + "; ".join(exceptions[:8])
                     + (" …" if len(exceptions) > 8 else ""))
    lines.append(f"errors: {len(errors)}")
    for e in errors[:20]:
        lines.append(f"  ! {e}")
    if len(errors) > 20:
        lines.append(f"  … 另有 {len(errors) - 20} 条")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="从 Markdown 生成题库索引")
    ap.add_argument("--scan", action="store_true", help="只读扫描，输出覆盖报告")
    ap.add_argument("--check", action="store_true", help="只校验，有错误 exit 1")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    questions, parse_issues = build_questions(cfg)
    qmap = {q["id"]: q for q in questions}
    sessions = build_sessions(cfg)
    scores = parse_scores()
    attempts, redo, issues, exceptions = build_attempts(sessions, qmap, cfg, scores)
    errors = validate(cfg, questions, sessions, attempts, redo, parse_issues + issues)

    print(report(cfg, questions, sessions, attempts, redo, errors, exceptions))

    if args.scan:
        return 0
    if args.check:
        return 1 if errors else 0
    if errors:
        print("\n有错误，未写出 index.json。先用 --scan 排查。", file=sys.stderr)
        return 1

    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    index = {
        "meta": {
            "generatedAt": now,
            "generator": "scripts/build_index.py",
            "sourceFiles": len(READ_FILES),
            "coverage": {
                "questions": len(questions),
                "attempts": len(attempts),
                "sessions": len(sessions),
                "redoRows": len(redo),
            },
            "timing": {m: sum(1 for s in sessions if s["timingMode"] == m)
                       for m in ("session", "per-question", "mixed", "none")},
            "errors": [],
        },
        "questions": questions,
        "sessions": sessions,
        "attempts": attempts,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写出 {rel(INDEX)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
