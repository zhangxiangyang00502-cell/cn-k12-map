"""步骤2：用"年级+课时名"把 topics 映射到教材树课时叶子；抓题目索引并匹配。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from smartedu_lib import RAW, fetch_multi, norm

BASE = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions"
GRADE_NUM = {"七年级": 7, "八年级": 8, "九年级": 9}


# 人工核对过教材目录后确认的别名匹配（topic名与课时名不一致但内容对应同一课时）。
# 格式: topicId -> (教材标题关键字, [课时名,...])
MANUAL_ALIAS = {
    "cn_df_zjsh_06": ("新教材-初中道德与法治统编版八年级上册", ["营造清朗空间"]),
    "cn_df_whzx_02": ("新教材-初中道德与法治统编版八年级上册", ["遵守规则"]),
    "cn_df_ydzr_04": ("新教材-初中道德与法治统编版八年级上册", ["守护正义"]),
    "cn_df_ydzr_06": ("新教材-初中道德与法治统编版八年级上册", ["奉献社会我践行"]),
    "cn_df_whgy_01": ("新教材-初中道德与法治统编版八年级上册", ["国家利益高于一切"]),
    "cn_df_xfzs_02": ("初中道德与法治统编版八年级下册", ["治国安邦的总章程"]),
    "cn_df_wmdsjj_02": ("初中道德与法治统编版九年级下册", ["复杂多变的关系"]),
    "cn_df_sjwt_05": ("初中道德与法治统编版九年级下册", ["中国的机遇与挑战"]),
    "cn_df_zhmr_01": ("新教材-初中道德与法治统编版七年级上册", ["探问人生目标", "树立正确的人生目标"]),
    "cn_df_czsk_07": ("新教材-初中道德与法治统编版七年级上册", ["集体生活成就我", "共建美好集体"]),
    "cn_df_ccwh_02": ("新教材-初中道德与法治统编版七年级下册", ["做核心思想理念的传承者"]),
    "cn_df_ccwh_03": ("新教材-初中道德与法治统编版七年级下册", ["影响深远的人文精神"]),
}


def main():
    topics = json.load(open("data/topics.json", encoding="utf-8"))["topics"]
    df = [t for t in topics if t["subject"] == "道德与法治" and t["gradeRangeStart"] in (7, 8, 9)]
    forest = json.load(open(os.path.join(RAW, "forest_df.json"), encoding="utf-8"))

    # 每个 topic 找最佳叶子：同学段年级；归一化后互为前缀/相等；新教材优先、长标题优先
    # mapping: topicId -> list of {tmId, leafId, ...}（一个 topic 可对应同课多个课时）
    mapping = {}
    unmatched = []
    for t in df:
        g = t["gradeRangeStart"]
        tn = norm(t["name"])
        cands = []
        for b in forest.values():
            if GRADE_NUM[b["grade"]] != g:
                continue
            for r in b["nodes"]:
                if not r["is_leaf"]:
                    continue
                ln = norm(r["title"])
                if not ln:
                    continue
                if tn == ln or tn.startswith(ln) or ln.startswith(tn):
                    score = (1 if b["new"] else 0, min(len(tn), len(ln)))
                    cands.append((score, b, r))
        if cands:
            cands.sort(key=lambda x: x[0], reverse=True)
            _, b, r = cands[0]
            mapping[t["id"]] = [{"tmId": b["tmId"], "leafId": r["id"],
                                 "leafTitle": r["title"], "path": r["path"],
                                 "book": b["title"]}]
        elif t["id"] in MANUAL_ALIAS:
            book_kw, leaf_names = MANUAL_ALIAS[t["id"]]
            hits = []
            for b in forest.values():
                if b["title"] != book_kw:
                    continue
                for r in b["nodes"]:
                    if r["is_leaf"] and norm(r["title"]) in [norm(n) for n in leaf_names]:
                        hits.append({"tmId": b["tmId"], "leafId": r["id"],
                                     "leafTitle": r["title"], "path": r["path"],
                                     "book": b["title"], "via": "manual_alias"})
            if hits:
                mapping[t["id"]] = hits
            else:
                unmatched.append(t)
                print("  [alias失效]", t["id"], book_kw, leaf_names)
        else:
            unmatched.append(t)

    print(f"topics={len(df)} 匹配={len(mapping)} 未匹配={len(unmatched)}")
    for t in unmatched[:20]:
        print("  未匹配:", t["id"], t["gradeRangeStart"], t["domain"], t["name"])

    with open(os.path.join(RAW, "topic_leaf_map.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=1)

    # 抓所有相关教材的题目索引
    tm_ids = sorted({m["tmId"] for ms in mapping.values() for m in ms})
    jobs = [(f"{BASE}/teachingmaterials/{tm}/national_resources/parts.json",
             f"parts_{tm}.json") for tm in tm_ids]
    fetch_multi(jobs)

    # parts.json -> part 文件 URL 列表 -> 题目条目
    part_jobs = []
    for tm in tm_ids:
        p = json.load(open(os.path.join(RAW, f"parts_{tm}.json"), encoding="utf-8"))
        urls = p.get("urls") if isinstance(p, dict) else p
        for i, u in enumerate(urls):
            part_jobs.append((u, f"qidx_{tm}_{i}.json"))
    fetch_multi(part_jobs)

    # 题目条目按 chapter_ids 末位叶子归到 topic
    leaf2topic = {}
    for tid, ms in mapping.items():
        for m in ms:
            leaf2topic.setdefault((m["tmId"], m["leafId"]), tid)
    qentries = {}  # (container_id, qid) -> {topicId, entry}
    n_total = n_matched = 0
    for tm in tm_ids:
        p = json.load(open(os.path.join(RAW, f"parts_{tm}.json"), encoding="utf-8"))
        urls = p.get("urls") if isinstance(p, dict) else p
        for i in range(len(urls)):
            arr = json.load(open(os.path.join(RAW, f"qidx_{tm}_{i}.json"), encoding="utf-8"))
            for e in arr:
                n_total += 1
                chs = e.get("chapter_ids") or []
                tid = leaf2topic.get((tm, chs[-1] if chs else None))
                if not tid:
                    continue
                n_matched += 1
                qentries[(e["container_id"], e["id"])] = {
                    "topicId": tid, "tmId": tm, "entry": e}
    print(f"题目条目总={n_total} 落到已匹配课时={n_matched} 去重后={len(qentries)}")
    with open(os.path.join(RAW, "qentries.json"), "w", encoding="utf-8") as f:
        json.dump([{"container_id": k[0], "qid": k[1], **v}
                   for k, v in qentries.items()], f, ensure_ascii=False)


if __name__ == "__main__":
    main()
