#!/usr/bin/env python3
"""下载题库教材总目录，找出道德与法治（初中 7/8/9，统编版）教材条目。缓存到 data/raw_smartedu/。"""
import json, os, time, urllib.request

ROOT = "/Users/yuanweisi/学习地图/cn-k12-map"
RAW = os.path.join(ROOT, "data", "raw_smartedu")
os.makedirs(RAW, exist_ok=True)

VERSION_URL = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/version/data_version.json"

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

ver = fetch(VERSION_URL, os.path.join(RAW, "tm_version.json"))
items = []
for u in ver["urls"]:
    part = fetch(u, os.path.join(RAW, "tm_" + os.path.basename(u)))
    if isinstance(part, list):
        items.extend(part)
    elif isinstance(part, dict) and "items" in part:
        items.extend(part["items"])
print("total textbooks:", len(items))

# 看一个条目结构
print(json.dumps(items[0], ensure_ascii=False)[:600])

def tag_names(item):
    out = []
    for t in item.get("tag_list", []):
        if isinstance(t, dict):
            out.append(t.get("tag_name") or t.get("name") or str(t))
        else:
            out.append(str(t))
    return out

df = []
for it in items:
    tags = tag_names(it)
    title = it.get("title", "")
    if "道德与法治" in title or "道德与法治" in " ".join(tags):
        df.append({"id": it.get("id"), "title": title, "tags": tags})

with open(os.path.join(RAW, "df_textbooks.json"), "w", encoding="utf-8") as f:
    json.dump(df, f, ensure_ascii=False, indent=1)
print("df textbooks:", len(df))
for d in df:
    print(d["id"], "|", d["title"], "|", " / ".join(d["tags"]))
