#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 data/index.json：按考点、错因、卷、题型筛题，输出可照着回原文核验的清单。

索引是导航层，题干不在这里；输出里的 source 指向 Markdown 原文。
用法示例：
    python3 scripts/query.py --topic 路程 --wrong-only
    python3 scripts/query.py --redo
    python3 scripts/query.py --error-tag 模型选错
    python3 scripts/query.py --question math-applied-distance-13
    python3 scripts/query.py --volume math-applied --type data-sufficiency
    python3 scripts/query.py --topic 路程 --csv > 路程错题.csv

零依赖，Python 3.11+。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "index.json"
CONFIG = ROOT / "data" / "volumes.json"

FIELDS = ["id", "number", "topic", "type", "answer", "attempts", "last", "errors", "source"]


def load():
    if not INDEX.exists():
        sys.exit("找不到 data/index.json，请先运行：python3 scripts/build_index.py")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def topic_matcher(term: str, aliases: dict):
    """中文考点名/简称/英文 slug 都能查。"""
    slug = aliases.get(term)
    if not slug:
        slug = next((v for k, v in aliases.items() if term == k or term in k), None)

    def match(q: dict) -> bool:
        if slug and f"-{slug}-" in q["id"]:
            return True
        return any(term in (q.get(k) or "") for k in ("topic", "section", "id"))

    return match


def summarize(q: dict, atts: list[dict]) -> dict:
    wrong = [a for a in atts if a["correct"] is False]
    tags = sorted({t for a in atts for t in (a.get("errorTags") or [])})
    last = "—"
    if atts:
        newest = max(atts, key=lambda a: a["date"])
        last = "✅" if newest["correct"] is True else ("❌" if newest["correct"] is False else "未判定")
        last += f" {newest['date']}"
    return {
        "id": q["id"], "number": q["number"], "topic": q["topic"], "type": q["type"],
        "answer": q["answer"] or "—", "attempts": len(atts), "last": last,
        "errors": "+".join(tags) or "—", "source": q["source"],
    }


def show_detail(q: dict, atts: list[dict]):
    print(f"ID      : {q['id']}")
    print(f"位置    : {q['source']}")
    print(f"卷/考点 : {q['volume']} / {q['section']}（{q['topic']}）")
    print(f"题型    : {q['type']}   可评分: {q['scorable']}")
    print(f"答案    : {q['answer'] or '—'}   来源: {q['answerSource'] or '—'}")
    if q.get("revision"):
        print(f"更正    : {q['revision']}")
    print(f"作答记录: {len(atts)} 条")
    for a in atts:
        mark = "✅" if a["correct"] is True else ("❌" if a["correct"] is False else "未判定")
        extra = ""
        if a.get("errorNote"):
            extra = f" | 错因 {a['errorTags']}：{a['errorNote']}"
        if a.get("score") is not None:
            extra = f" | 估分 {a['score']}/{a['scoreMax']}"
        print(f"  {a['date']} {a['sessionId']} 答 {a['userAnswer'] or '—'} / 正解 {a['correctAnswer'] or '—'} {mark}{extra}")
        print(f"    {a['source']}")
    print("题干与选项不在索引中，请按上面的 source 回 Markdown 查看。")


def main() -> int:
    ap = argparse.ArgumentParser(description="查询题库索引（导航层，题干见 source）")
    ap.add_argument("--topic", help="考点中文名/简称/slug，如 路程、线规、distance")
    ap.add_argument("--volume", help="卷 slug，如 math-applied")
    ap.add_argument("--type", dest="qtype", help="题型，如 data-sufficiency")
    ap.add_argument("--question", help="精确题目 ID，输出完整档案")
    ap.add_argument("--error-tag", dest="error_tag", help="错因标签，如 模型选错")
    ap.add_argument("--wrong-only", action="store_true", help="只列做过且错过的题")
    ap.add_argument("--redo", action="store_true", help="只列待重做清单里的题")
    ap.add_argument("--csv", action="store_true", help="输出 CSV（正确转义 LaTeX 与中文标点）")
    ap.add_argument("--limit", type=int, default=0, help="最多输出 N 条，0 = 不限")
    args = ap.parse_args()

    d = load()
    questions = {q["id"]: q for q in d["questions"]}
    by_q: dict[str, list[dict]] = {}
    for a in d["attempts"]:
        by_q.setdefault(a["questionId"], []).append(a)

    if args.question:
        if args.question not in questions:
            print(f"没有这个 ID：{args.question}", file=sys.stderr)
            return 1
        show_detail(questions[args.question], by_q.get(args.question, []))
        return 0

    aliases = json.loads(CONFIG.read_text(encoding="utf-8")).get("topicAliases", {})
    match_topic = topic_matcher(args.topic, aliases) if args.topic else None
    rows = []
    for q in d["questions"]:
        atts = by_q.get(q["id"], [])
        if args.volume and q["volume"] != args.volume:
            continue
        if args.qtype and q["type"] != args.qtype:
            continue
        if match_topic and not match_topic(q):
            continue
        if args.wrong_only and not any(a["correct"] is False for a in atts):
            continue
        if args.redo and not any(a.get("errorNote") for a in atts):
            continue
        if args.error_tag and not any(args.error_tag in (a.get("errorTags") or []) for a in atts):
            continue
        rows.append(summarize(q, atts))
    if args.limit:
        rows = rows[:args.limit]

    if args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    else:
        if not rows:
            print("没有匹配的题目。")
            return 0
        widths = [max(len(str(r[f])) for r in rows) for f in FIELDS]
        widths = [min(w, 46) for w in widths]
        header = "  ".join(f.ljust(widths[i]) for i, f in enumerate(FIELDS))
        print(header)
        print("-" * len(header))
        for r in rows:
            print("  ".join(str(r[f])[:46].ljust(widths[i]) for i, f in enumerate(FIELDS)))
        print(f"\n共 {len(rows)} 题。题干见 source；需要表格视图可加 --csv。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
