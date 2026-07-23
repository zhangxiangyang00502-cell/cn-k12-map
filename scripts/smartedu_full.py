"""步骤4（全量）：抓全部已匹配题目详情，解析过滤，输出 data/quiz_smartedu.json。"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from smartedu_lib import RAW, fetch_multi
from smartedu_parse import parse_question, entry_is_single_choice

DETAIL = "https://bdcs-file-1.ykt.cbern.com.cn/zxx/api_static/questions/{c}_{i}/data.json"
OUT = "data/quiz_smartedu.json"


def main():
    entries = json.load(open(os.path.join(RAW, "qentries.json"), encoding="utf-8"))
    skip_tag = [e for e in entries if not entry_is_single_choice(e["entry"])]
    cands = [e for e in entries if entry_is_single_choice(e["entry"])]
    print(f"条目 {len(entries)}，题型标签排除 {len(skip_tag)}，待抓详情 {len(cands)}")

    jobs = [(DETAIL.format(c=e["container_id"], i=e["qid"]),
             f"q_{e['container_id']}_{e['qid']}.json") for e in cands]
    fetch_multi(jobs)

    questions, rejects = [], collections.Counter()
    seen_q = set()
    for e in cands:
        path = os.path.join(RAW, f"q_{e['container_id']}_{e['qid']}.json")
        if not os.path.exists(path):
            rejects["download_failed"] += 1
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            rejects["bad_json"] += 1
            continue
        parsed, reason = parse_question(data)
        if not parsed:
            rejects[reason] += 1
            continue
        key = (e["topicId"], parsed["q"][:60])
        if key in seen_q:
            rejects["duplicate"] += 1
            continue
        seen_q.add(key)
        questions.append({"topicId": e["topicId"], "type": "choice", **parsed})

    questions.sort(key=lambda x: x["topicId"])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"questions": questions}, f, ensure_ascii=False, indent=1)

    per_topic = collections.Counter(q["topicId"] for q in questions)
    mapping = json.load(open(os.path.join(RAW, "topic_leaf_map.json"), encoding="utf-8"))
    covered = set(per_topic)
    print(f"\n输出 {OUT}: {len(questions)} 题")
    print("过滤原因:", dict(rejects))
    print(f"有题 topic: {len(covered)}/{len(mapping)}（已匹配课时）")
    for tid, n in sorted(per_topic.items()):
        print(f"  {tid}: {n}")


if __name__ == "__main__":
    main()
