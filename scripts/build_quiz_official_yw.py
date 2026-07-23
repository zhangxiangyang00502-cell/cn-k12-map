#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 data/raw_smartedu/yw_parsed.json 里的官方语文题匹配到 topics.json 语文知识主题节点，
输出 data/quiz_official_yw.json + data/quiz_official_yw_report.json。

匹配策略（语文节点是"知识主题"命名，与教材课文名无法精确对应，故采用规则分类）：
  1. 垃圾题过滤（听力/视频题、空选项）
  2. 题干/选项中出现名著书名 → 对应"整本书阅读"节点
  3. 题干题型关键词（字音字形/词语成语/病句/标点/修辞/语法/文学常识/文言实虚词/诗歌鉴赏）→ 对应知识节点
  4. 课文内容理解题 → 按课文文体（文言文/古诗词/说明文/新闻/议论文/小说/童话寓言/记叙文）映射
  5. 年级严格约束：题目年级必须落在节点 gradeRangeStart..End 内；每个节点最多 8 题
"""
import json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw_smartedu")

topics = [t for t in json.load(open(os.path.join(ROOT, "data", "topics.json"), encoding="utf-8"))["topics"]
          if t.get("subject") == "语文"]
tby = {t["id"]: t for t in topics}
qs = json.load(open(os.path.join(RAW, "yw_parsed.json"), encoding="utf-8"))

# ---------- 1. 垃圾题过滤 ----------
JUNK_RE = re.compile(r"听到的内容|听录音|听力材料|请点击观看|请点击收听|看视频|听音频|根据听到的")
def is_junk(q):
    blob = q["q"] + " " + " ".join(q["options"])
    if JUNK_RE.search(blob):
        return "audio_video"
    opts = [re.sub(r"^[A-D]\.\s*", "", o).strip() for o in q["options"]]
    if any(not o or len(o) < 1 for o in opts):
        return "empty_option"
    if len(set(opts)) < len(opts):
        return "dup_option"
    return None

# ---------- 2. 书名 → 整本书阅读节点 ----------
BOOK_MAP = [
    ("西游记", "cn_yw_zs_08"), ("朝花夕拾", "cn_yw_zs_09"), ("骆驼祥子", "cn_yw_zs_10"),
    ("红星照耀中国", "cn_yw_zs_11"), ("昆虫记", "cn_yw_zs_12"), ("水浒传", "cn_yw_zs_13"),
    ("儒林外史", "cn_yw_zs_14"), ("简·爱", "cn_yw_zs_15"), ("简爱", "cn_yw_zs_15"),
    ("钢铁是怎样炼成的", "cn_yw_zs_16"), ("乡土中国", "cn_yw_zs_18"), ("红楼梦", "cn_yw_zs_19"),
]

# ---------- 3. 课文文体识别（标题子串匹配）----------
def any_in(ch, words):
    return any(w in ch for w in words)

WY_文言文 = ["卖油翁","诫子书","世说新语","孙权劝学","陋室铭","爱莲说","河中石兽","桃花源记","小石潭记",
    "核舟记","岳阳楼记","醉翁亭记","湖心亭看雪","鱼我所欲也","送东阳马生序","曹刿论战","邹忌讽齐王",
    "出师表","虽有嘉肴","《礼记》","礼记","大道之行也","马说","愚公移山","周亚夫军细柳","生于忧患",
    "富贵不能淫","自相矛盾","杨氏之子","伯牙鼓琴","书戴嵩画牛","陈太丘与友期","咏雪","杞人忧天","穿井得一人"]
GS_古诗词 = ["古诗","诗词","清平乐","宿新市徐公店","从军行","古代诗歌","唐诗","木兰诗","观沧海",
    "次北固山下","天净沙","词四首","曲","延安，我把你追寻"]  # 注意"曲"单独弱，靠前面强词
SM_说明文 = ["中国石拱桥","苏州园林","大自然的语言","阿西莫夫","恐龙","大雁归来","时间的脚印","蝉",
    "梦回繁华","飞向蓝天的恐龙","琥珀","太阳","松鼠","故宫博物院","被压扁的沙子"]
XW_新闻 = ["消息二则","首届诺贝尔奖","飞天凌空","一着惊海天","国行公祭","人民解放军"]
YL_议论文 = ["敬业与乐业","就英法联军","论教养","精神的三间小屋","中国人失掉自信力","怀疑与学问",
    "谈创造性思维","创造宣言","谈读书","不求甚解","山水画的意境","无言之美","驱遣我们的想象",
    "有为有不为","纪念白求恩","最苦与最乐","庆祝奥林匹克","我一生中的重要抉择","应有格物致知精神","最后一次讲演"]
XS_小说 = ["社戏","故乡","我的叔叔于勒","孤独之旅","智取生辰纲","范进中举","三顾茅庐","刘姥姥",
    "孔乙己","变色龙","溜索","蒲柳人家","台阶","驿路梨花","带上她的眼睛","小英雄雨来","草船借箭",
    "猴王出世","景阳冈","红楼春趣","山地回忆","芦花鞋","我们家的男子汉","剃头大师","西门豹治邺","田忌赛马"]
TH_童话寓言 = ["卖火柴的小女孩","那一定会很好","在牛肚子里旅行","一块奶酪","总也倒不了的老屋",
    "一个豆荚里的五粒豆","海的女儿","女娲造人","皇帝的新装","寓言四则","蚊子和狮子","池子与河流","我不能失信"]
SW_散文 = ["春","济南的冬天","雨的四季","散步","秋天的怀念","背影","白杨礼赞","昆明的雨","藤野先生",
    "回忆我的母亲","安塞腰鼓","灯笼","在长江源头","壶口瀑布","一滴水经过丽江","井冈翠竹","紫藤萝瀑布",
    "一棵小桃树","叶圣陶先生","阿长与","老王","我的白鸽","青春之光","再塑生命","猫","观潮","天窗",
    "繁星","三月桃花水","乡下人家","火烧云","童年的水墨画","肥皂泡","牧场之国","月是故乡明","梅花魂"]

# ---------- 4. 题干题型 → 候选节点（按年级在赋值时过滤）----------
def cand_by_grade(ids, g):
    return [i for i in ids if i in tby and tby[i]["gradeRangeStart"] <= g <= tby[i]["gradeRangeEnd"]]

CATS = [
    # (name, regex, candidate topic ids in preference order)
    # 顺序即优先级：文言/诗歌类先于一般词语类，避免文言实词题落入"词语运用"
    ("文言实词虚词", r"通假|词类活用|古今义|古今异义|加点词.*(意思|解释|意义|用法)|加点(词|实词).*(意思|解释|意义)|解释.*加点|文言|实词|虚词|用法(相同|不同|一致)|意义和用法",
     ["cn_yw_jl_13","cn_yw_jl_14","cn_yw_wx_19","cn_yw_wx_18"]),
    ("诗歌鉴赏", r"诗句|诗歌|诗词|古诗|意象|意境",
     ["cn_yw_wx_16","cn_yw_wx_17","cn_yw_wx_03","cn_yw_jl_15","cn_yw_wx_29"]),
    ("字音字形", r"注音|读音|字音|字形|书写.*正确|错别字",
     ["cn_yw_py_01","cn_yw_py_02","cn_yw_py_03","cn_yw_py_06","cn_yw_py_09","cn_yw_py_10",
      "cn_yw_py_15","cn_yw_py_17","cn_yw_py_16","cn_yw_py_18"]),
    ("成语", r"成语",
     ["cn_yw_jl_03","cn_yw_jl_17","cn_yw_jl_19"]),
    ("名言谚语", r"谚语|歇后语|名言|俗语",
     ["cn_yw_jl_04","cn_yw_jl_02"]),
    ("词语运用", r"词语.*(运用|使用|恰当)|依次填入|选词填空|近义词|词语.*意思",
     ["cn_yw_jl_01","cn_yw_jl_02","cn_yw_jl_19","cn_yw_jl_17"]),
    ("病句", r"语病|病句", ["cn_yw_jl_08"]),
    ("标点", r"标点", ["cn_yw_jl_05"]),
    ("修辞", r"修辞", ["cn_yw_jl_07","cn_yw_jl_12"]),
    ("语法", r"词性|短语(结构|类型)|句子成分|复句|提取.*主干",
     ["cn_yw_jl_09","cn_yw_jl_10","cn_yw_jl_11","cn_yw_jl_06"]),
    ("古诗文背诵", r"默写|补写|填写.*(名句|诗句)|背诵",
     ["cn_yw_jl_15"]),
    ("文学文化常识", r"文学常识|文化常识|作家作品|文学体裁|(作者|朝代|出处).{0,20}(正确|有误|对应|搭配)",
     ["cn_yw_jl_16","cn_yw_jl_17"]),
    ("口语交际", r"口语交际|表达.*得体|劝说|转述",
     ["cn_yw_sy_15","cn_yw_sy_16","cn_yw_sy_14"]),
    ("综合性学习", r"综合性学习|活动.*(方案|策划)|调查.*报告",
     ["cn_yw_kx_01","cn_yw_kx_02","cn_yw_kx_04","cn_yw_sy_13"]),
    ("内容理解", r"(理解|分析|概括|内容).*(正确|不正确|有误|恰当|准确)",
     []),  # 由课文文体决定
]

# 文体 → 候选节点
GENRE_MAP = [
    ("文言文", lambda ch: any_in(ch, WY_文言文),
     ["cn_yw_wx_18","cn_yw_wx_19","cn_yw_wx_20","cn_yw_jl_13"]),
    ("古诗词", lambda ch: any_in(ch, GS_古诗词),
     ["cn_yw_wx_03","cn_yw_wx_16","cn_yw_wx_17","cn_yw_jl_15"]),
    ("说明文", lambda ch: any_in(ch, SM_说明文),
     ["cn_yw_sy_06","cn_yw_sy_07"]),
    ("新闻", lambda ch: any_in(ch, XW_新闻),
     ["cn_yw_sy_09"]),
    ("议论文", lambda ch: any_in(ch, YL_议论文),
     ["cn_yw_sb_05","cn_yw_sb_06","cn_yw_sb_07","cn_yw_sb_08","cn_yw_sb_09"]),
    ("小说", lambda ch: any_in(ch, XS_小说),
     ["cn_yw_wx_15","cn_yw_wx_10","cn_yw_wx_13"]),
    ("童话寓言", lambda ch: any_in(ch, TH_童话寓言),
     ["cn_yw_wx_02","cn_yw_wx_09","cn_yw_sb_04"]),
    ("散文记叙", lambda ch: any_in(ch, SW_散文),
     ["cn_yw_wx_14","cn_yw_wx_11","cn_yw_wx_10","cn_yw_wx_13","cn_yw_wx_25"]),
]
# 内容理解题兜底（按年级）
NARRATIVE_FALLBACK = ["cn_yw_wx_10","cn_yw_wx_09","cn_yw_wx_13","cn_yw_wx_02","cn_yw_wx_14",
                      "cn_yw_sy_04","cn_yw_sy_03","cn_yw_sy_05","cn_yw_sb_01","cn_yw_sb_02"]

def classify(q):
    """返回 (candidates, rule, category)。candidates 已按年级过滤。"""
    g = q["grade"]
    blob = q["q"] + " " + " ".join(q["options"])
    ch = q["chapter_title"]
    # 规则2：名著书名
    for name, tid in BOOK_MAP:
        if name in blob and tid in tby and tby[tid]["gradeRangeStart"] <= g <= tby[tid]["gradeRangeEnd"]:
            return [tid], "book_title", f"名著《{name}》"
    # 规则3：题干题型
    for cname, pat, ids in CATS:
        if re.search(pat, q["q"]):
            if cname == "内容理解":
                break  # 交给规则4
            c = cand_by_grade(ids, g)
            if c:
                return c, "stem_category", cname
            # 题型明确但该年级区间无对应节点：不再按课文文体兜底，避免错配
            return [], "no_grade_node", cname
    # 规则4：课文文体
    for gname, fn, ids in GENRE_MAP:
        if fn(ch):
            c = cand_by_grade(ids, g)
            if c:
                return c, "chapter_genre", gname
    c = cand_by_grade(NARRATIVE_FALLBACK, g)
    if c:
        return c, "narrative_fallback", "记叙文兜底"
    return [], "unmatched", ""

# ---------- 5. 过滤 + 去重 + 分配 ----------
junk = collections.Counter()
clean = []
seen = set()
for q in qs:
    j = is_junk(q)
    if j:
        junk[j] += 1
        continue
    key = re.sub(r"\s+", "", q["q"])[:60] + re.sub(r"\s+", "", q["options"][0])[:20]
    if key in seen:
        junk["dup"] += 1
        continue
    seen.add(key)
    clean.append(q)

CAP = 8
count = collections.Counter()
assigned = []       # (q, topicId, rule, category)
unmatched = []
# 高优先级规则先分配，保证强匹配先占位
PRIORITY = {"book_title": 0, "stem_category": 1, "chapter_genre": 2, "narrative_fallback": 3}
tagged = []
for q in clean:
    cands, rule, cat = classify(q)
    tagged.append((PRIORITY.get(rule, 9), q, cands, rule, cat))
tagged.sort(key=lambda x: x[0])

for pri, q, cands, rule, cat in tagged:
    placed = None
    for tid in cands:
        if count[tid] < CAP:
            placed = tid
            break
    if placed:
        count[placed] += 1
        assigned.append((q, placed, rule, cat))
    else:
        unmatched.append((q, rule, cat, cands))

# ---------- 6. 输出 ----------
out_qs = []
for q, tid, rule, cat in assigned:
    out_qs.append({
        "topicId": tid, "type": "choice",
        "q": q["q"], "options": q["options"], "answer": q["answer"],
        "explain": q["explain"],
    })

out_path = os.path.join(ROOT, "data", "quiz_official_yw.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"questions": out_qs}, f, ensure_ascii=False, indent=1)

# 覆盖率：有题年级 = 平台语文题库实际覆盖的年级
avail_grades = sorted(set(q["grade"] for q in clean))
reachable = [t for t in topics if any(t["gradeRangeStart"] <= g <= t["gradeRangeEnd"] for g in avail_grades)]
covered = [t for t in topics if count[t["id"]] > 0]
covered_reachable = [t for t in reachable if count[t["id"]] > 0]

unmatched_reasons = collections.Counter()
for q, rule, cat, cands in unmatched:
    if rule == "unmatched":
        unmatched_reasons["无匹配规则/年级区间无对应节点"] += 1
    elif not cands:
        unmatched_reasons[f"{cat}:年级区间无对应节点"] += 1
    else:
        unmatched_reasons[f"{cat}:候选节点已满(8题上限)"] += 1

samples = []
for q, tid, rule, cat in assigned[:2]:
    samples.append({"topicId": tid, "rule": rule, "category": cat, "grade": q["grade"],
                    "q": q["q"], "options": q["options"], "answer": q["answer"],
                    "explain": q["explain"], "source_chapter": q["chapter_path"], "tm": q["tm_title"]})

report = {
    "source": "国家中小学智慧教育平台(basic.smartedu.cn) 官方题库 - 统编版语文",
    "textbooks_with_questions": sorted(set(q["tm_title"] for q in clean)),
    "grades_with_questions": avail_grades,
    "raw_index_items": 827,
    "parsed_unique": len(qs),
    "junk_filtered": dict(junk),
    "after_filter": len(clean),
    "assigned": len(assigned),
    "unmatched": len(unmatched),
    "unmatched_reasons": dict(unmatched_reasons),
    "cap_per_topic": CAP,
    "coverage": {
        "nodes_total_yuwen": len(topics),
        "nodes_reachable_by_available_grades": len(reachable),
        "nodes_with_questions": len(covered),
        "coverage_all": f"{len(covered)}/{len(topics)}",
        "coverage_reachable": f"{len(covered_reachable)}/{len(reachable)}",
    },
    "rule_distribution": dict(collections.Counter(r for _, _, r, _ in assigned)),
    "per_topic_counts": {tid: count[tid] for tid in sorted(count) if count[tid] > 0},
    "unmatched_samples": [
        {"grade": q["grade"], "chapter": q["chapter_path"], "q": q["q"][:80], "rule": rule, "category": cat}
        for q, rule, cat, _ in unmatched[:20]
    ],
    "samples": samples,
    "matching_notes": [
        "语文节点按知识主题命名（学习任务群），与教材课文名不一一对应，无法做'年级+课时名'精确匹配，采用规则分类匹配。",
        "年级严格约束：题目年级须落在节点年级区间内；如 g7-9 的字音字形题因字词类节点最高只到 g6 而无法匹配。",
        "五四学制小学册课文与六三统编版一致，年级号相同，题目并入对应年级。",
        "平台语文官方题库只覆盖 1/3/4/5/7/8/9 年级，且 7-9 年级题量占绝对多数；g2/g6/g10-12 无题源。",
    ],
}
rep_path = os.path.join(ROOT, "data", "quiz_official_yw_report.json")
with open(rep_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("assigned:", len(assigned), "unmatched:", len(unmatched))
print("coverage all:", report["coverage"]["coverage_all"], "reachable:", report["coverage"]["coverage_reachable"])
print("rules:", report["rule_distribution"])
print("unmatched reasons:", dict(unmatched_reasons))
print("wrote:", out_path, rep_path)
