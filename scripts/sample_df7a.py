#!/usr/bin/env python3
"""小样本验证：七上章节树 + 题目索引 + 3 道题详情解析。"""
import json, os, re, sys, time, urllib.request
from html import unescape

ROOT = "/Users/yuanweisi/学习地图/cn-k12-map"
RAW = os.path.join(ROOT, "data", "raw_smartedu")
os.makedirs(RAW, exist_ok=True)
os.makedirs(os.path.join(RAW, "qdetails"), exist_ok=True)

TM7A = "d350d7ac-8166-4b30-88d4-1fe48457f8e8"  # 新教材-初中道法统编版七上

def fetch(url, path, retries=3):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
            time.sleep(0.2)
            return data
        except Exception as e:
            last = e
            time.sleep(1 + i)
    raise RuntimeError(f"fetch failed {url}: {last}")

TAG_RE = re.compile(r"<[^>]+>")
def strip_html(s):
    if not s:
        return ""
    s = unescape(s)
    s = re.sub(r"<(img|table|tbody|tr|td|th)[^>]*>", " ", s, flags=re.I)
    s = TAG_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

# 1. 章节树
tree = fetch(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/trees/{TM7A}.json",
             os.path.join(RAW, f"tree_{TM7A}.json"))
print("tree top-level units:", len(tree))
def walk(nodes, depth=0, out=None):
    for n in nodes:
        out.append((depth, n.get("id"), n.get("title")))
        walk(n.get("child_nodes") or [], depth + 1, out)
    return out
lines = walk(tree, 0, [])
for d, i, t in lines[:30]:
    print("  " * d + f"[{i[:8]}] {t}")
print("... total nodes:", len(lines))

# 2. 题目索引
parts = fetch(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/{TM7A}/national_resources/parts.json",
              os.path.join(RAW, f"parts_{TM7A}.json"))
print("\nparts.json:", json.dumps(parts, ensure_ascii=False)[:500])
urls = parts if isinstance(parts, list) else parts.get("urls", [])
qitems = []
for u in urls:
    part = fetch(u, os.path.join(RAW, "qidx_" + os.path.basename(u)))
    qitems.extend(part if isinstance(part, list) else part.get("items", []))
print("question index items:", len(qitems))
print(json.dumps(qitems[0], ensure_ascii=False)[:700])

# 3. 前三道题详情
for q in qitems[:3]:
    cid, qid = q["container_id"], q["id"]
    det = fetch(f"https://bdcs-file-1.ykt.cbern.com.cn/zxx/api_static/questions/{cid}_{qid}/data.json",
                os.path.join(RAW, "qdetails", f"{cid}_{qid}.json"))
    c = det.get("content", {})
    title = strip_html(c.get("title", ""))
    items = c.get("items") or []
    choices = []
    for it in items:
        for ch in it.get("choices") or []:
            choices.append((ch.get("identifier"), strip_html(ch.get("text", ""))))
    corrects = []
    for r in c.get("responses") or []:
        corrects.extend(r.get("corrects") or [])
    fb = ""
    for f_ in c.get("feedbacks") or []:
        fb = strip_html(f_.get("content", ""))
        break
    tags = [t.get("tag_name", "") if isinstance(t, dict) else str(t) for t in q.get("tag_list", [])]
    print("\n=== q:", qid, "| tags:", tags, "| chapters:", q.get("chapter_ids"))
    print("Q:", title)
    for ident, txt in choices:
        print(f"  {ident}. {txt}")
    print("ANS:", corrects)
    print("EXPLAIN:", fb[:200])
