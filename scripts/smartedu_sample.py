"""步骤3（小样本）：取新教材七上的题目详情，打印3道人工核对。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from smartedu_lib import RAW, fetch_json
from smartedu_parse import parse_question, entry_is_single_choice

DETAIL = "https://bdcs-file-1.ykt.cbern.com.cn/zxx/api_static/questions/{c}_{i}/data.json"


def main():
    entries = json.load(open(os.path.join(RAW, "qentries.json"), encoding="utf-8"))
    mapping = json.load(open(os.path.join(RAW, "topic_leaf_map.json"), encoding="utf-8"))
    new7 = {tid for tid, ms in mapping.items()
            for m in ms if m["book"].startswith("新教材") and "七年级" in m["book"]}
    sample = [e for e in entries if e["topicId"] in new7][:5]
    print(f"新教材七年级条目 {sum(1 for e in entries if e['topicId'] in new7)}，取 {len(sample)} 条样本\n")
    ok = 0
    for e in sample:
        url = DETAIL.format(c=e["container_id"], i=e["qid"])
        data = fetch_json(url, cache_name=f"q_{e['container_id']}_{e['qid']}.json")
        if data is None:
            print("[下载失败]", url)
            continue
        print("=" * 60)
        print("topicId:", e["topicId"], "| 题型标签:",
              [t.get("tag_name") for t in e["entry"].get("tag_list") or []])
        parsed, reason = parse_question(data)
        if not parsed:
            print("跳过原因:", reason)
            continue
        ok += 1
        print("Q:", parsed["q"][:120])
        for o in parsed["options"]:
            print("  ", o[:100])
        print("答案:", parsed["answer"], "| 解析:", parsed["explain"][:100])
        if ok >= 3:
            break


if __name__ == "__main__":
    main()
