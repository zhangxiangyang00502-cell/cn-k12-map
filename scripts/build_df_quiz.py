#!/usr/bin/env python3
"""全量抓取：初中道法统编版 7-9 年级 6 册官方题库 -> quiz 格式。
输出: data/raw_smartedu/quiz_df_official.json （新文件，不动 data/quiz.json）
缓存: data/raw_smartedu/ （章节树/索引/详情均落盘，重复运行不重复请求）
"""
import json, os, re, time, urllib.request
from html import unescape

ROOT = "/Users/yuanweisi/学习地图/cn-k12-map"
RAW = os.path.join(ROOT, "data", "raw_smartedu")
DET = os.path.join(RAW, "qdetails")
os.makedirs(DET, exist_ok=True)

TEXTBOOKS = {
    ("7上", 7): "d350d7ac-8166-4b30-88d4-1fe48457f8e8",
    ("7下", 7): "0950ee38-88ea-4da9-8da9-bafb9dade3e1",
    ("8上", 8): "a7269cde-d3a4-452b-8013-2e3a44d4382e",
    ("8下", 8): "02d175b7-a0d7-4ae2-8e52-d946bf8f73f4",
    ("9上", 9): "399e395b-ed98-44b2-903f-39f41f26a548",
    ("9下", 9): "bec0aa15-d286-4f1b-98cc-143b91c00af5",
}
# 新教材题库为空时的旧版回退（同为统编版官方题，按课时标题匹配到新教材节点）
FALLBACK = {
    ("8上", 8): "955fadcc-fb53-4225-b4d9-af191d7a1553",
    ("8下", 8): "998d1fd7-8912-48ed-affd-4242ced28894",
}
# 高置信课时标题别名（教材改课时改了框题名，内容对应同一知识点）
ALIAS = {
    (7, "让家更美好"): "cn_df_czsk_02",
    (7, "集体生活成就我"): "cn_df_czsk_07",
    (7, "共建美好集体"): "cn_df_czsk_07",
    (7, "探问人生目标"): "cn_df_zhmr_01",
    (7, "树立正确的人生目标"): "cn_df_zhmr_01",
    (8, "我与社会"): "cn_df_zjsh_02",
    (8, "在社会中成长"): "cn_df_zjsh_03",
    (8, "合理利用网络"): "cn_df_zjsh_06",
    (8, "遵守规则"): "cn_df_whzx_02",
    (8, "国家好大家才会好"): "cn_df_whgy_01",
    (8, "树立总体国家安全观"): "cn_df_whgy_05",
    (8, "自由平等的真谛"): "cn_df_ydzr_01",
    (8, "自由平等的追求"): "cn_df_ydzr_02",
    (8, "公平正义的守护"): "cn_df_ydzr_04",
    (8, "服务社会"): "cn_df_ydzr_06",
    (8, "根本政治制度"): "cn_df_gjzd_01",
    (8, "党的主张和人民意志的统一"): "cn_df_xfzs_01",
    (9, "复杂多变的关系"): "cn_df_wmdsjj_02",
    (9, "少年当自强"): "cn_df_zxwl_01",
    (9, "中国的机遇与挑战"): "cn_df_sjwt_05",
    (9, "学无止境"): "cn_df_zxwl_04",
    (9, "走向未来"): "cn_df_zxwl_05",
}

def fetch(url, path, retries=3):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            os.remove(path)
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
    print(f"  !! fetch failed {url}: {last}")
    return None

TAG_RE = re.compile(r"<[^>]+>")
def strip_html(s):
    if not s:
        return ""
    s = unescape(s).replace("\xa0", " ").replace("\u200b", "")
    s = TAG_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()

def has_unrenderable(raw):
    return bool(re.search(r"<(img|table)\b", raw or "", re.I))

def norm(s):
    s = re.sub(r"[\s\u3000]+", "", s or "")
    return re.sub(r"[，。：:；;、（）()《》<>“”\"'‘’·—\-_!?！？.．]", "", s)

# ---------- topics 映射： (grade, norm(base_name)) -> topicId ----------
topics = json.load(open(os.path.join(ROOT, "data", "topics.json")))["topics"]
df_topics = [t for t in topics if t["subject"] == "道德与法治"]
tmap = {}
for t in df_topics:
    base = re.split(r"[：:]", t["name"])[0]
    tmap[(t["gradeRangeStart"], norm(base))] = t["id"]
print("df topics:", len(df_topics))

# ---------- 逐册处理 ----------
out = []          # 最终题目
unmatched = []    # (book, leaf_title, count)
stats = {}
seen_qids = set()

for (label, grade), tm in list(TEXTBOOKS.items()):
    tree = fetch(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/trees/{tm}.json",
                 os.path.join(RAW, f"tree_{tm}.json"))
    node_title = {}   # node id -> title
    def walk(nodes):
        for n in nodes:
            node_title[n["id"]] = n.get("title", "")
            walk(n.get("child_nodes") or [])
    walk(tree or [])

    parts = fetch(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/{tm}/national_resources/parts.json",
                  os.path.join(RAW, f"parts_{tm}.json"))
    urls = parts if isinstance(parts, list) else (parts or {}).get("urls", [])
    idx = []
    for u in urls:
        p = fetch(u, os.path.join(RAW, f"qidx_{tm}_" + os.path.basename(u)))
        if p:
            idx.extend(p if isinstance(p, list) else p.get("items", []))

    # 新教材题库为空 -> 回退旧版教材
    fb_note = ""
    if not idx and (label, grade) in FALLBACK:
        tm = FALLBACK[(label, grade)]
        fb_note = " [回退旧版]"
        tree = fetch(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/trees/{tm}.json",
                     os.path.join(RAW, f"tree_{tm}.json"))
        node_title = {}
        walk(tree or [])
        parts = fetch(f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/{tm}/national_resources/parts.json",
                      os.path.join(RAW, f"parts_{tm}.json"))
        urls = parts if isinstance(parts, list) else (parts or {}).get("urls", [])
        for u in urls:
            p = fetch(u, os.path.join(RAW, f"qidx_{tm}_" + os.path.basename(u)))
            if p:
                idx.extend(p if isinstance(p, list) else p.get("items", []))

    n_kept = n_skip_type = n_skip_media = n_skip_ans = n_unmatched = 0
    leaf_counter = {}
    for q in idx:
        qid, cid = q.get("id"), q.get("container_id")
        if not qid or qid in seen_qids:
            continue
        tags = {t.get("tag_name", "") if isinstance(t, dict) else str(t) for t in q.get("tag_list", [])}
        if "单选题" not in tags or "多选题" in tags or "主观题" in tags:
            n_skip_type += 1
            continue
        det = fetch(f"https://bdcs-file-1.ykt.cbern.com.cn/zxx/api_static/questions/{cid}_{qid}/data.json",
                    os.path.join(DET, f"{cid}_{qid}.json"))
        if not det:
            continue
        c = det.get("content", {})
        raw_title = c.get("title", "") or ""
        choices = []
        for it in c.get("items") or []:
            for ch in it.get("choices") or []:
                choices.append((ch.get("identifier"), ch.get("text", "") or ""))
        # 媒体/表格过滤（题干、选项、prompt、description 原始 HTML）
        prompt_blobs = [c.get("description", "") or ""]
        for it in c.get("items") or []:
            prompt_blobs.append(it.get("prompt", "") or "")
        if (has_unrenderable(raw_title) or any(has_unrenderable(t) for _, t in choices)
                or any(has_unrenderable(p) for p in prompt_blobs)):
            n_skip_media += 1
            continue
        # 题干引用图片但图已被过滤的（“观察右图/漫画”类）也跳过
        prompt_txt = " ".join(strip_html(p) for p in prompt_blobs)
        if re.search(r"(右图|下图|如图|漫画|观察图|示意图)", raw_title + prompt_txt) and not re.search(r"<img", raw_title):
            # prompt 里没有可渲染的图片内容，但题干依赖图——保守起见仅当 prompt 曾被过滤时跳
            if any("<img" in p or "<table" in p for p in prompt_blobs):
                n_skip_media += 1
                continue
        ans = []
        for r in c.get("responses") or []:
            ans.extend(r.get("corrects") or [])
        ans = [a for a in ans if isinstance(a, str) and a.strip() in "ABCDEFGH" and len(a.strip()) == 1]
        if len(ans) != 1 or ans[0].strip() not in "ABCD" or len(choices) < 2:
            n_skip_ans += 1
            continue
        answer = ans[0].strip()
        # 选项规范化：identifier 必须是字母；重排成 A/B/C...
        idents = [i for i, _ in choices]
        if sorted(idents) != sorted("ABCD"[: len(choices)]):
            # identifier 非标准 A..N，跳过
            n_skip_ans += 1
            continue
        options = [f"{i}. {strip_html(t)}" for i, t in choices]
        if any(len(o) <= 3 for o in options):
            n_skip_ans += 1
            continue
        qtext = strip_html(raw_title)
        qtext = re.sub(r"^\d+\s*[.、．]\s*", "", qtext)           # 去掉题号
        qtext = re.sub(r"^[（(](改编|原创|名校模拟)[)）]\s*", "", qtext)
        explain = ""
        for fb in c.get("feedbacks") or []:
            explain = strip_html(fb.get("content", ""))
            if explain:
                break
        if answer not in idents:
            n_skip_ans += 1
            continue

        # 匹配 topic：chapter_ids 最后一个通常是叶子
        topic_id = None
        leaf_title = None
        chs = q.get("chapter_ids") or []
        for chid in reversed(chs):
            title = node_title.get(chid)
            if not title:
                continue
            title = title.strip()
            if (grade, title) in ALIAS:
                topic_id = ALIAS[(grade, title)]
                leaf_title = leaf_title or title
                break
            key = (grade, norm(title))
            if key in tmap:
                topic_id = tmap[key]
                break
            if leaf_title is None:
                leaf_title = title
        if not topic_id and leaf_title and (grade, leaf_title.strip()) in ALIAS:
            topic_id = ALIAS[(grade, leaf_title.strip())]
        if not topic_id:
            # 再用叶子标题对全表做一次包含式匹配（同学段）
            cand = norm(leaf_title) if leaf_title else ""
            if cand:
                for (g, name), tid in tmap.items():
                    if g == grade and (cand in name or name in cand):
                        topic_id = tid
                        break
        if not topic_id:
            n_unmatched += 1
            leaf_counter[leaf_title or "?"] = leaf_counter.get(leaf_title or "?", 0) + 1
            continue

        seen_qids.add(qid)
        out.append({
            "topicId": topic_id,
            "type": "choice",
            "q": qtext,
            "options": options,
            "answer": answer,
            "explain": explain or f"本题考查{leaf_title or '本课时'}相关内容。",
            "_book": label,
            "_src": f"smartedu:{cid}_{qid}",
        })
        n_kept += 1

    stats[label] = {"index": len(idx), "kept": n_kept, "skip_type": n_skip_type,
                    "skip_media": n_skip_media, "skip_bad_ans": n_skip_ans, "unmatched": n_unmatched}
    for lt, cnt in leaf_counter.items():
        unmatched.append((label, lt, cnt))
    print(f"{label}: index={len(idx)} kept={n_kept} skip_type={n_skip_type} media={n_skip_media} bad_ans={n_skip_ans} unmatched={n_unmatched}")

# 去掉内部字段，写最终文件
final = [{k: v for k, v in q.items() if not k.startswith("_")} for q in out]
outpath = os.path.join(RAW, "quiz_df_official.json")
with open(outpath, "w", encoding="utf-8") as f:
    json.dump({"questions": final}, f, ensure_ascii=False, indent=1)

# 覆盖率
covered = {q["topicId"] for q in final}
all_df = {t["id"] for t in df_topics}
print("\n== 总计 ==")
print("题目总数:", len(final))
print(f"节点覆盖: {len(covered)}/{len(all_df)}")
print("\n未覆盖节点:")
for t in df_topics:
    if t["id"] not in covered:
        print(" ", t["id"], t["gradeRangeStart"], t["domain"], t["name"])
print("\n匹配失败的课时标题 top20:")
for b, lt, cnt in sorted(unmatched, key=lambda x: -x[2])[:20]:
    print(f"  [{b}] {lt} x{cnt}")
print("\n输出:", outpath)
