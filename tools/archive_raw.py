"""原文归档：把每天你和我说的话，按天存一份原文。

不摘要、不概括、不删。为的是应付一件事：
**记忆被压缩时丢的正是"为什么"，而原话里带着它。**

抄自 dsh-world 的设计（"全部原文都留着，需要时按原话去找"）。
数据来源：会话日志里的 user/message（只认主人）和 assistant/message。

用法：
  python 原文归档.py            # 跑最近一个会话
  python 原文归档.py --days 7   # 只保留最近 7 天的归档文件
"""

import datetime as dt
import glob
import json
import os
import sys

import zstandard as zstd

SESSIONS = r"C:\Users\PC\.dsh\sessions"
OUT = r"C:\Users\PC\.dsh\profiles\desktop\.记忆\原文"


def newest_session():
    files = glob.glob(os.path.join(SESSIONS, "**", "session.v4.jsonl.zstd"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None


def extract(path):
    """返回 [(date, role, text)]，只留主人和我的正文。"""
    raw = zstd.ZstdDecompressor().stream_reader(open(path, "rb")).read().decode("utf-8", "replace")
    out = []
    for line in raw.splitlines():
        if '"user/message"' not in line and '"assistant/message"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = o.get("type")
        ts = o.get("time")
        if not ts:
            continue
        d = dt.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        data = o.get("data") or {}
        content = data.get("content")
        text = ""
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text += c.get("text", "")
        elif isinstance(content, str):
            text = content
        if not text:
            continue
        if t == "user/message":
            kind = (data.get("source") or {}).get("kind", "")
            if kind != "plugin:dsh-onebot":
                continue          # 定时提醒、自动任务不算"我们说的话"
        else:
            pass
        out.append((d, "我" if t == "assistant/message" else "主人", text.strip()))
    return out


def main():
    path = newest_session()
    if not path:
        print("没有会话日志")
        return
    rows = extract(path)
    os.makedirs(OUT, exist_ok=True)
    by_day = {}
    for d, who, text in rows:
        by_day.setdefault(d, []).append((who, text))

    for d, items in by_day.items():
        p = os.path.join(OUT, f"{d}.md")
        # 已经有了就合并：按行去重，旧的在前
        old = []
        if os.path.exists(p):
            old = [ln for ln in open(p, encoding="utf-8").read().split("\n") if ln.startswith("- ")]
        new = [f"- **{who}**：{text.replace(chr(10), ' ')[:400]}" for who, text in items]
        merged = []
        for ln in old + new:
            if ln not in merged:
                merged.append(ln)
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"# {d} 原文\n\n> 一字不改。合并去重，不删。\n\n")
            f.write("\n".join(merged) + "\n")
        print(f"{d}: {len(merged)} 条")

    if "--days" in sys.argv:
        keep = int(sys.argv[sys.argv.index("--days") + 1])
        files = sorted(glob.glob(os.path.join(OUT, "*.md")), reverse=True)
        for old in files[keep:]:
            os.remove(old)
            print("删掉旧归档:", os.path.basename(old))


if __name__ == "__main__":
    main()
