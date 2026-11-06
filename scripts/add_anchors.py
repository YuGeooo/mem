#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给题库 Markdown 的题号行末加 ID 锚点（幂等，只追加结构信息，不改题意）。

锚点一律放在行尾，保持 `**N.**` / `N. ` 在行首，以免破坏题号清点正则。
用法：
    python3 scripts/add_anchors.py --dry-run   # 只看会加多少，不写文件
    python3 scripts/add_anchors.py             # 实际写入
重复运行不会重复添加；已有锚点但 ID 不符会报错并退出 1。

ID 规则复用 scripts/build_index.py，避免两处各写一套。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index as bi  # noqa: E402

ROOT = bi.ROOT
ANCHOR_RE = re.compile(r'<a id="([^"]+)"></a>')
BOLD = re.compile(r"^\*\*(\d+)\.\*\*")
NUM = re.compile(r"^(\d+)\.\s")
MATH_SECTION = re.compile(r"^## 【考点(\d+)】")

cfg = bi.json.loads((bi.DATA / "volumes.json").read_text(encoding="utf-8"))
TOPIC_BY_SEC = {t["section"]: t["topic"] for t in cfg["mathTopics"]}

ENGLISH_SUBJECTIVE = {
    46: "2025-english-translation",
    47: "2025-english-writing-a",
    48: "2025-english-writing-b",
}


def id_2024(n: int, _sec: int) -> str:
    if n == 56:
        return "2024-exam-essay1"
    if n == 57:
        return "2024-exam-essay2"
    return bi.qid_2024(n)


def id_english(n: int, _sec: int) -> str:
    return ENGLISH_SUBJECTIVE[n] if n in ENGLISH_SUBJECTIVE else bi.qid_english(n)


def id_math(n: int, sec: int) -> str:
    return bi.qid_math(TOPIC_BY_SEC[sec], n)


RULES = [
    {"file": "2024年管综真题/paper.md", "pattern": BOLD, "id": id_2024, "expect": 57},
    {"file": "2025年英语二/paper.md", "pattern": NUM, "id": id_english, "expect": 48},
    {"file": "形式逻辑与综合推理/形式逻辑与综合推理一.md",
     "pattern": BOLD, "id": lambda n, s: bi.qid_formal(1, n), "expect": 15},
    {"file": "形式逻辑与综合推理/形式逻辑与综合推理二.md",
     "pattern": BOLD, "id": lambda n, s: bi.qid_formal(2, n), "expect": 15},
    {"file": "专项训练二-五大条件类推理题/paper.md",
     "pattern": NUM, "id": lambda n, s: bi.qid_reasoning(n), "expect": 30},
    {"file": "数学应用题/应用题.md", "pattern": BOLD, "id": id_math,
     "sectionPattern": MATH_SECTION, "expect": 81},
]


def process(rule: dict, dry: bool) -> tuple[int, int, list[str]]:
    path = ROOT / rule["file"]
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    errors: list[str] = []
    seen: dict[str, int] = {}
    sec = 0
    added = skipped = 0
    for lineno, line in enumerate(lines, 1):
        if "sectionPattern" in rule:
            sm = rule["sectionPattern"].match(line)
            if sm:
                sec = int(sm.group(1))
        m = rule["pattern"].match(line)
        if not m:
            out.append(line)
            continue
        n = int(m.group(1))
        try:
            qid = rule["id"](n, sec)
        except KeyError:
            errors.append(f"{rule['file']}:{lineno} 未找到考点 {sec} 的 topic")
            out.append(line)
            continue
        if qid in seen:
            errors.append(f"{rule['file']}:{lineno} 重复 ID {qid}（首次在 {seen[qid]} 行）")
        else:
            seen[qid] = lineno
        existing = ANCHOR_RE.search(line)
        if existing:
            if existing.group(1) != qid:
                errors.append(f"{rule['file']}:{lineno} 已有锚点 {existing.group(1)}，应为 {qid}")
            skipped += 1
            out.append(line)
        else:
            out.append(line + f' <a id="{qid}"></a>')
            added += 1
    matched = added + skipped
    if matched != rule["expect"]:
        errors.append(f"{rule['file']}: 题号行应为 {rule['expect']}，实际 {matched}")
    if not dry and added and not errors:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return added, skipped, errors


def main() -> int:
    ap = argparse.ArgumentParser(description="给题库题号行末加 ID 锚点（幂等）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = ap.parse_args()

    total_add = total_skip = 0
    all_errors: list[str] = []
    for rule in RULES:
        added, skipped, errors = process(rule, args.dry_run)
        total_add += added
        total_skip += skipped
        all_errors.extend(errors)
        print(f'{rule["file"]:42s} 新增 {added:3d} / 已有 {skipped:3d}')
    print(f"合计: 新增 {total_add}，已有 {total_skip}，错误 {len(all_errors)}")
    for e in all_errors:
        print(f"  ! {e}")
    if all_errors:
        return 1
    if args.dry_run:
        print("（--dry-run，未写入任何文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
