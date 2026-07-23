#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从国家中小学智慧教育平台(basic.smartedu.cn)抓取统编版语文官方题库，
转为项目 quiz 格式。只读 topics.json，不写任何已有文件。

输出:
  data/quiz_official_yw.json         {"questions":[...]}
  data/quiz_official_yw_report.json  运行报告
缓存:
  data/raw_smartedu/                 原始抓取缓存
"""
import json, os, re, sys, time, random, html
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw_smartedu")
os.makedirs(RAW, exist_ok=True)

HOSTS = ["bdcs-file-1.ykt.cbern.com.cn", "s-file-1.ykt.cbern.com.cn", "s-file-2.ykt.cbern.com.cn"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def fetch_json(url, cache_name=None, retries=3):
    """带缓存+重试的 JSON 抓取。cache_name 相对 RAW 目录。"""
    if cache_name:
        path = os.path.join(RAW, cache_name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            if cache_name:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            time.sleep(0.2)
            return data
        except Exception as e:
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed {url}: {last}")

# ---------- 1. 教材总目录 ----------
ver = fetch_json("https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/version/data_version.json", "tm_version.json")
tms = []
for i, u in enumerate(ver["urls"]):
    tms += fetch_json(u, f"tm_part_{i}.json")

def dim(t, d):
    for tag in t.get("tag_list", []):
        if tag.get("tag_dimension_id") == d:
            return tag.get("tag_name")
    return None

GRADE_MAP = {"一年级":1,"二年级":2,"三年级":3,"四年级":4,"五年级":5,"六年级":6,
             "七年级":7,"八年级":8,"九年级":9,
             "高一":10,"高二":11,"高三":12}

def parse_grade(t):
    g = dim(t, "zxxnj") or ""
    if g in GRADE_MAP:
        return GRADE_MAP[g]
    m = re.search(r"(高一|高二|高三)", t.get("title",""))
    if m:
        return GRADE_MAP[m.group(1)]
    if "选择性必修 下" in t.get("title","") or "选择性必修下" in t.get("title",""):
        return 12
    return None

# 选统编版语文教材：平台上语文题库覆盖稀疏，凡是有题的册都收
# （含五四学制小学册：课文与六三统编版一致，年级号相同；新旧版并存的全收，后面按题干去重）
cands = []
for t in tms:
    title = t.get("title", "")
    if dim(t, "zxxxk") != "语文":
        continue
    if "统编" not in title:
        continue
    g = parse_grade(t)
    if g is None:
        # 五四学制小学: tag 年级可能是"三年级"等，parse_grade 已覆盖 zxxnj；此处兜底标题
        m = re.search(r"([一二三四五])年级", title)
        if m and ("五•四" in title or "五四" in title):
            g = GRADE_MAP[m.group(1) + "年级"]
    if g is None:
        continue
    half = "上" if "上册" in title else ("下" if "下册" in title else ("中" if "中册" in title else "?"))
    new = 1 if title.startswith("新教材") else 0
    cands.append({"id": t["id"], "title": title, "grade": g, "half": half, "new": new,
                  "update": t.get("update_time", "")})

# 先去重同 tmId，再全部保留（后续按题目有无实际数据自然过滤）
seen_tm = {}
for c in cands:
    seen_tm[c["id"]] = c
books = sorted(seen_tm.values(), key=lambda x: (x["grade"], x["half"], -x["new"]))
print(f"选中教材 {len(books)} 册:")
for b in books:
    print(" ", b["grade"], b["half"], b["title"], b["id"][:8])

# ---------- 2. 逐册抓章节树+题目索引 ----------
def get_tree(tm_id):
    return fetch_json(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/trees/{tm_id}.json",
                      f"trees/{tm_id}.json")

def get_parts(tm_id):
    d = fetch_json(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/{tm_id}/national_resources/parts.json",
                   f"parts/{tm_id}.json")
    urls = d if isinstance(d, list) else d.get("urls", [])
    items = []
    for i, u in enumerate(urls):
        items += fetch_json(u, f"qidx/{tm_id}_{i}.json")
    return items

def flatten_tree(nodes, parent_titles=()):
    """返回 {node_id: (title, full_path)}"""
    out = {}
    for n in nodes or []:
        title = n.get("title", "")
        path = parent_titles + (title,)
        out[n.get("id")] = (title, path)
        out.update(flatten_tree(n.get("child_nodes"), path))
    return out

all_qrefs = []   # {container_id,id,grade,tm_title,chapter_title,chapter_path,tags,qnum}
for b in books:
    try:
        tree = get_tree(b["id"])
        node_map = flatten_tree(tree if isinstance(tree, list) else tree.get("child_nodes", []))
        qitems = get_parts(b["id"])
    except Exception as e:
        print(f"!! 教材 {b['title']} 抓取失败: {e}")
        continue
    n_q = 0
    for q in qitems:
        ch_ids = q.get("chapter_ids") or []
        leaf = ch_ids[-1] if ch_ids else None
        ch_title, ch_path = node_map.get(leaf, ("", ()))
        tags = [t.get("tag_name","") for t in q.get("tag_list",[])]
        all_qrefs.append({
            "container_id": q.get("container_id"), "id": q.get("id"),
            "grade": b["grade"], "tm_title": b["title"],
            "chapter_title": ch_title,
            "chapter_path": "/".join(ch_path),
            "tags": tags,
            "qnum": (q.get("custom_properties") or {}).get("qb_qu_num"),
        })
        n_q += 1
    print(f"  {b['title']}: 题目索引 {n_q} 条")

print(f"题目索引合计 {len(all_qrefs)} 条")
with open(os.path.join(RAW, "yw_qrefs.json"), "w", encoding="utf-8") as f:
    json.dump(all_qrefs, f, ensure_ascii=False, indent=1)

# ---------- 3. 只保留候选单选题，抓详情 ----------
def is_candidate(r):
    tags = r["tags"]
    if any("多选" in t or "主观" in t or "填空" in t or "解答" in t or "判断" in t for t in tags):
        return False
    return any("单选" in t for t in tags) or not any("题" in t for t in tags)

cands_q = [r for r in all_qrefs if is_candidate(r)]
print(f"单选候选 {len(cands_q)} 条")

TAG_RE = re.compile(r"<[^>]+>")
def strip_html(s):
    if not s:
        return ""
    s = html.unescape(s)
    s = TAG_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()

def fetch_detail(r):
    path = f"details/{r['container_id']}_{r['id']}.json"
    full = os.path.join(RAW, path)
    if os.path.exists(full) and os.path.getsize(full) > 0:
        with open(full, encoding="utf-8") as f:
            return r, json.load(f)
    last = None
    for host in HOSTS:
        url = f"https://{host}/zxx/api_static/questions/{r['container_id']}_{r['id']}/data.json"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                time.sleep(0.2)
                return r, data
            except Exception as e:
                last = e
                time.sleep(0.3 * (attempt + 1))
    return r, {"__error__": str(last)}

def parse_detail(r, d):
    """返回规范化题目 dict 或 None(跳过原因写入 r['_skip'])"""
    if "__error__" in d:
        r["_skip"] = "fetch_error:" + d["__error__"]
        return None
    content = d.get("content") or d
    raw_title = content.get("title") or ""
    if "<img" in raw_title or "<table" in raw_title:
        r["_skip"] = "stem_has_img_or_table"
        return None
    q_text = strip_html(raw_title)
    if len(q_text) < 4:
        r["_skip"] = "stem_too_short"
        return None
    # options
    items = content.get("items") or []
    choices = []
    for it in items:
        for c in it.get("choices") or []:
            ident = c.get("identifier", "")
            txt = c.get("text") or ""
            if "<img" in txt or "<table" in txt:
                r["_skip"] = "option_has_img_or_table"
                return None
            choices.append((ident, strip_html(txt)))
    if len(choices) < 2:
        r["_skip"] = "too_few_options"
        return None
    # answer
    corrects = []
    for resp in content.get("responses") or []:
        corrects += resp.get("corrects") or []
    if len(corrects) != 1:
        r["_skip"] = "not_single_answer"
        return None
    ans = corrects[0]
    letters = [c[0] for c in choices]
    if ans not in letters or ans not in list("ABCDEFGH"):
        r["_skip"] = "bad_answer:" + str(ans)
        return None
    # 只保留 A-D 四选项以内的题（答案必须在 A-D 内）
    if len(choices) > 4 or ans not in list("ABCD")[:len(choices)]:
        r["_skip"] = "options_not_abcd"
        return None
    explain = ""
    fbs = content.get("feedbacks") or []
    # 优先 showAnswer（答案解析），否则取第一个非空 feedback
    for fb in fbs:
        if fb.get("identifier") == "showAnswer" and strip_html(fb.get("content") or ""):
            explain = strip_html(fb["content"])
            break
    if not explain:
        for fb in fbs:
            if strip_html(fb.get("content") or ""):
                explain = strip_html(fb["content"])
                break
    options = [f"{ident}. {txt}" for ident, txt in choices]
    return {
        "q": q_text, "options": options, "answer": ans,
        "explain": explain, "grade": r["grade"],
        "chapter_title": r["chapter_title"], "chapter_path": r["chapter_path"],
        "tm_title": r["tm_title"],
        "src_id": f'{r["container_id"]}_{r["id"]}',
    }

parsed, skipped = [], {}
done = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(fetch_detail, r) for r in cands_q]
    for fut in as_completed(futs):
        r, d = fut.result()
        q = parse_detail(r, d)
        if q:
            parsed.append(q)
        else:
            skipped[r.get("_skip", "unknown").split(":")[0]] = skipped.get(r.get("_skip", "unknown").split(":")[0], 0) + 1
        done += 1
        if done % 200 == 0:
            print(f"  详情进度 {done}/{len(cands_q)}")

print(f"解析成功 {len(parsed)} 题; 跳过: {skipped}")
with open(os.path.join(RAW, "yw_parsed.json"), "w", encoding="utf-8") as f:
    json.dump(parsed, f, ensure_ascii=False, indent=1)

# 去重（同题干）
seen = set()
uniq = []
for q in parsed:
    k = re.sub(r"\s+", "", q["q"])[:80]
    if k in seen:
        continue
    seen.add(k)
    uniq.append(q)
print(f"去重后 {len(uniq)} 题")

# ---------- 4. 打印 3 道样本人工核对 ----------
print("\n===== 样本核对 =====")
for q in uniq[:3]:
    print("年级", q["grade"], "|", q["tm_title"], "|", q["chapter_path"])
    print("Q:", q["q"][:120])
    for o in q["options"]:
        print("  ", o[:80])
    print("答案:", q["answer"], "| 解析:", q["explain"][:100])
    print("---")
