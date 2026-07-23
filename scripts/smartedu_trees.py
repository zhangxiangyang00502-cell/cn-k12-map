"""步骤1：选定目标教材（初中道法统编版7-9年级），抓章节树，扁平化课时叶子。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from smartedu_lib import RAW, fetch_json, fetch_multi

BASE = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions"


def load_catalog():
    items = []
    for p in (100, 101, 102):
        items += json.load(open(os.path.join(RAW, f"tm_part_{p}.json"), encoding="utf-8"))
    return items


def tags(it):
    return {t["tag_dimension_id"]: t["tag_name"] for t in it["tag_list"]}


def select_textbooks():
    """初中（非五四学制）道德与法治 统编版 七/八/九年级 上下册。"""
    out = []
    for it in load_catalog():
        tg = tags(it)
        if tg.get("zxxxk") != "道德与法治":
            continue
        if tg.get("zxxxd") != "初中":
            continue
        grade = tg.get("zxxnj", "")
        ce = tg.get("zxxcc", "")
        if grade not in ("七年级", "八年级", "九年级") or ce not in ("上册", "下册"):
            continue
        new = it["title"].startswith("新教材")
        out.append({"tmId": it["id"], "title": it["title"], "grade": grade,
                    "ce": ce, "new": new})
    return out


def flatten(tree):
    """返回 [{id,title,path,is_leaf}]，path 含单元>课>课时。"""
    rows = []

    def walk(node, path):
        title = node.get("title", "")
        children = node.get("child_nodes") or []
        cur = path + [title]
        rows.append({"id": node.get("id"), "title": title, "path": cur,
                     "is_leaf": not children})
        for c in children:
            walk(c, cur)

    for top in tree:
        walk(top, [])
    return rows


def main():
    books = select_textbooks()
    print(f"目标教材 {len(books)} 本：")
    for b in books:
        print(" ", b["title"], b["tmId"][:13])
    jobs = [(f"{BASE}/trees/{b['tmId']}.json", f"tree_{b['tmId']}.json") for b in books]
    fetch_multi(jobs)
    forest = {}
    for b in books:
        data = json.load(open(os.path.join(RAW, f"tree_{b['tmId']}.json"), encoding="utf-8"))
        rows = flatten(data)
        b["nodes"] = rows
        forest[b["tmId"]] = b
        leaves = [r for r in rows if r["is_leaf"]]
        print(f"{b['title']}: 节点{len(rows)} 叶子{len(leaves)}")
    with open(os.path.join(RAW, "forest_df.json"), "w", encoding="utf-8") as f:
        json.dump(forest, f, ensure_ascii=False)
    # 打印新教材七上前两单元结构供人工核对
    for b in books:
        if b["new"] and b["grade"] == "七年级" and b["ce"] == "上册":
            for r in b["nodes"][:30]:
                print("  " * (len(r["path"]) - 1) + r["title"], "[leaf]" if r["is_leaf"] else "")
            break


if __name__ == "__main__":
    main()
