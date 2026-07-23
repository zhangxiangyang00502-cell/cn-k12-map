#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_courses.py — 枚举国家中小学智慧教育平台(basic.smartedu.cn)官方视频课程包
(national_lesson)，为道德与法治(7-9年级统编版)和语文(统编版,覆盖 topics.json
出现的年级)的每个课时生成播放页深链，产出 data/resources_courses.json 与
data/resources_courses_report.json。

接口（全部免登录，已探明）：
  教材目录:   /zxx/ndrs/national_lesson/teachingmaterials/version/data_version.json
  课程章节树: /zxx/ndrs/national_lesson/trees/{tmId}.json
  课程资源索引: /zxx/ndrs/national_lesson/teachingmaterials/{tmId}/resources/parts.json
  课程包详情: /zxx/ndrv2/national_lesson/resources/details/{activityId}.json
  播放页: https://basic.smartedu.cn/syncClassroom/classActivity?activityId=..&chapterId=..&teachingmaterialId=..&fromPrepare=0&classHourId=lesson_1
"""
import json, os, re, sys, time, unicodedata
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw_smartedu')
os.makedirs(RAW, exist_ok=True)

HOSTS = ['s-file-1', 's-file-2']
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

def fetch(url, cache_name=None, binary=False):
    """带缓存 + 重试3次 + 双 host 回退的 GET。"""
    if cache_name:
        p = os.path.join(RAW, cache_name)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return f.read()
    last = None
    for attempt in range(3):
        u = url
        for h in HOSTS:
            uu = re.sub(r'https://s-file-\d\.', f'https://{h}.', u)
            try:
                req = urllib.request.Request(uu, headers=UA)
                with urllib.request.urlopen(req, timeout=40) as r:
                    body = r.read()
                if cache_name:
                    with open(os.path.join(RAW, cache_name), 'wb') as f:
                        f.write(body)
                time.sleep(0.2)
                return body
            except Exception as e:
                last = e
        time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f'fetch failed: {url} -> {last}')

def fetch_json(url, cache_name=None):
    return json.loads(fetch(url, cache_name))

# ---------- 教材选择 ----------
GRADE_NUM = {'一年级':1,'二年级':2,'三年级':3,'四年级':4,'五年级':5,'六年级':6,
             '七年级':7,'八年级':8,'九年级':9,'高一':10,'高二':11}

def tagmap(x):
    return {t['tag_dimension_id']: t['tag_name'] for t in x.get('tag_list', [])}

def load_catalog():
    items = []
    for i in (100, 101, 102):
        p = os.path.join(RAW, f'tm_part_{i}.json')
        if not os.path.exists(p):
            u = f'https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/teachingmaterials/part_{i}.json'
            fetch(u, f'tm_part_{i}.json')
        items += json.load(open(p))
    return items

def select_textbooks(items):
    """返回 [(tmId, title, subject, grade, ce(册), edition)] 列表。"""
    picked = []
    # --- 道法 7-9 六册：7/8 用新教材(2024/2025)，9 用带"同步课资源视图"的旧教材 ---
    df_pref = {
        (7,'上册'): 'd350d7ac-8166-4b30-88d4-1fe48457f8e8',
        (7,'下册'): '0950ee38-88ea-4da9-8da9-bafb9dade3e1',
        (8,'上册'): 'a7269cde-d3a4-452b-8013-2e3a44d4382e',
        (8,'下册'): '02d175b7-a0d7-4ae2-8e52-d946bf8f73f4',
        (9,'上册'): '399e395b-ed98-44b2-903f-39f41f26a548',
        (9,'下册'): 'bec0aa15-d286-4f1b-98cc-143b91c00af5',
    }
    by_id = {x['id']: x for x in items}
    for (g, ce), tid in df_pref.items():
        x = by_id[tid]
        tm = tagmap(x)
        picked.append((tid, x['title'], '道德与法治', g, ce, tm.get('zxxxjjc') or ('同步课资源视图' if 'tagView' in tm else '')))
    # --- 语文：按 (年级, 册) 分组，新教材优先，其次带同步课资源视图 ---
    groups = {}
    for x in items:
        tm = tagmap(x)
        if tm.get('zxxxk') != '语文' or tm.get('zxxbb') != '统编版':
            continue
        if tm.get('zxxxd') not in ('小学', '初中', '高中'):
            continue
        g = GRADE_NUM.get(tm.get('zxxnj'))
        ce = tm.get('zxxcc')
        if not g or not ce:
            continue
        key = (g, ce)
        score = (1 if tm.get('zxxxjjc') == '新教材' else 0, 1 if 'tagView' in tm else 0)
        cur = groups.get(key)
        if not cur or score > cur[0]:
            groups[key] = (score, x)
    for (g, ce), (_, x) in sorted(groups.items()):
        tm = tagmap(x)
        picked.append((x['id'], x['title'], '语文', g, ce, tm.get('zxxxjjc') or ''))
    return picked

# ---------- 章节树 ----------
def load_tree(tm_id):
    return fetch_json(
        f'https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/trees/{tm_id}.json',
        f'nl_tree_{tm_id}.json')

def lesson_map(tree):
    """chapter_id -> {'unit','lesson','depth'}；叶子(课时)与中间层都收录。"""
    m = {}
    def walk(node, unit, lesson, depth):
        title = re.sub(r'\s+', ' ', node.get('title') or '').strip()
        kids = node.get('child_nodes') or []
        if depth == 0:
            unit = title
        elif depth == 1:
            lesson = title
        m[node['id']] = {'unit': unit, 'lesson': lesson or title, 'title': title, 'depth': depth, 'leaf': not kids}
        for c in kids:
            walk(c, unit, lesson, depth + 1)
    for top in tree:
        walk(top, '', '', 0)
    return m

# ---------- 课程资源 ----------
def load_activities(tm_id):
    parts = fetch_json(
        f'https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/teachingmaterials/{tm_id}/resources/parts.json',
        f'nl_parts_{tm_id}.json')
    if isinstance(parts, dict):
        parts = parts.get('urls', [])
    out = []
    def one(u):
        name = 'nl_res_' + re.sub(r'[^A-Za-z0-9_.-]', '_', u.split('/zxx/')[-1])
        return fetch_json(u, name)
    with ThreadPoolExecutor(max_workers=6) as ex:
        for arr in ex.map(one, parts):
            out += arr
    return out

# ---------- 题目匹配 ----------
def norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    return ''.join(ch for ch in s if not unicodedata.category(ch).startswith(('P', 'Z', 'C')))

def build_topic_index():
    topics = json.load(open(os.path.join(ROOT, 'data', 'topics.json')))['topics']
    return topics

def match_topic(activities_title, subject, grade, topics_by_sg):
    """在同学科、同学段的 topic 中匹配课时名。返回 (topic, level) 或 (None, None)。"""
    cands = topics_by_sg.get(subject, [])
    na = norm(activities_title)
    if not na:
        return None, None
    best = None
    for tp in cands:
        if not (tp['gradeRangeStart'] <= grade <= tp['gradeRangeEnd']):
            continue
        nt = norm(tp['name'])
        if not nt:
            continue
        if nt == na:
            return tp, 'exact'
        lvl = None
        if len(nt) >= 4 and len(na) >= 4:
            if nt.startswith(na) or na.startswith(nt):
                lvl = ('prefix', min(len(nt), len(na)))
            elif nt in na or na in nt:
                lvl = ('contains', min(len(nt), len(na)))
        if lvl and (not best or lvl[1] > best[1][1]):
            best = (tp, lvl)
    if best:
        return best[0], best[1][0]
    return None, None

def bigram_dice(a, b):
    def bg(s):
        return {s[i:i+2] for i in range(len(s)-1)} if len(s) >= 2 else ({s} if s else set())
    A, B = bg(a), bg(b)
    return 2 * len(A & B) / (len(A) + len(B)) if (A or B) else 0.0

def near_miss_hint(lesson_title, subject, grade, topics_by_sg, topn=1):
    """信息性提示：与课时名 bigram 相似度最高的同学科 topic（不参与正式匹配）。"""
    na = norm(lesson_title)
    if len(na) < 3:
        return None
    best = None
    for tp in topics_by_sg.get(subject, []):
        if not (tp['gradeRangeStart'] <= grade <= tp['gradeRangeEnd']):
            continue
        nt = norm(tp['name'])
        if not nt:
            continue
        s = bigram_dice(na, nt)
        if best is None or s > best[0]:
            best = (s, tp)
    if best and best[0] >= 0.45:
        return {'topicId': best[1]['id'], 'topicName': best[1]['name'], 'similarity': round(best[0], 3)}
    return None

def main():
    items = load_catalog()
    books = select_textbooks(items)
    print(f'selected textbooks: {len(books)}')
    for b in books:
        print('  ', b[3], b[4], b[2], b[5], b[1], b[0])

    topics = build_topic_index()
    topics_by_sg = {}
    for tp in topics:
        if tp['subject'] in ('道德与法治', '语文'):
            topics_by_sg.setdefault(tp['subject'], []).append(tp)

    all_lessons = []   # 每课时: {tm,book,subject,grade,ce,unit,lesson,chapter_id,activities:[...]}
    failures = []
    for tm_id, title, subject, grade, ce, edition in books:
        try:
            tree = load_tree(tm_id)
        except Exception as e:
            failures.append({'tmId': tm_id, 'title': title, 'stage': 'tree', 'error': str(e)})
            continue
        lmap = lesson_map(tree)
        try:
            acts = load_activities(tm_id)
        except Exception as e:
            failures.append({'tmId': tm_id, 'title': title, 'stage': 'resources', 'error': str(e)})
            continue
        # 按叶子章节归组
        by_leaf = {}
        for a in acts:
            ch = a.get('chapter_ids') or []
            if not ch:
                continue
            leaf = ch[-1]
            node = lmap.get(leaf)
            if not node:
                node = lmap.get(ch[0])
            if not node:
                continue
            teachers = '、'.join(t.get('name') for t in (a.get('teacher_list') or []) if t.get('name'))
            by_leaf.setdefault(leaf, []).append({
                'activityId': a['id'],
                'title': a.get('title') or '',
                'teachers': teachers,
                'chapter_id': leaf,
            })
        for leaf, arr in by_leaf.items():
            node = lmap[leaf]
            all_lessons.append({
                'tmId': tm_id, 'book': title, 'subject': subject, 'grade': grade, 'ce': ce,
                'unit': node['unit'], 'lesson': node['lesson'], 'leaf_title': node['title'],
                'chapter_id': leaf,
                'activities': arr,
            })
        print(f'  {title}: lessons_with_res={len(by_leaf)} activities={len(acts)}')

    # 匹配 topicId
    resources = {}   # topicId -> [items]
    matched_lessons, unmatched_lessons = [], []
    match_levels = {}
    for ls in all_lessons:
        # 优先用叶子节点(框题/课时)名匹配；兜底用活动标题、再用上一级课题名
        tp, level = match_topic(ls['leaf_title'], ls['subject'], ls['grade'], topics_by_sg)
        if not tp:
            for a in ls['activities']:
                tp, level = match_topic(a['title'], ls['subject'], ls['grade'], topics_by_sg)
                if tp:
                    break
        if not tp:
            # 上一级课题名兜底；跳过过于泛化的节点名，避免误配（如"整本书阅读"）
            GENERIC = {'整本书阅读', '口语交际', '写作', '单元思考与行动', '语文园地',
                       '综合性学习', '识字', '汉语拼音', '中考复习', '其他专题'}
            pl = norm(ls['lesson'])
            if pl and pl not in GENERIC and len(pl) >= 6:
                tp, level = match_topic(ls['lesson'], ls['subject'], ls['grade'], topics_by_sg)
        if tp:
            matched_lessons.append({**{k: ls[k] for k in ('book','grade','ce','unit','lesson','leaf_title')},
                                    'topicId': tp['id'], 'topicName': tp['name'], 'level': level})
            match_levels[level] = match_levels.get(level, 0) + 1
            for a in ls['activities']:
                is_zhuanti = a['title'].startswith('专题')
                ttl = f"{a['title']}（{a['teachers']}）" if a['teachers'] else a['title']
                url = ('https://basic.smartedu.cn/syncClassroom/classActivity'
                       f"?activityId={a['activityId']}&chapterId={a['chapter_id']}"
                       f"&teachingmaterialId={ls['tmId']}&fromPrepare=0&classHourId=lesson_1")
                resources.setdefault(tp['id'], []).append({
                    'type': 'course', 'title': ttl, 'url': url,
                    'source': '国家中小学智慧教育平台',
                    'note': '人教社官方专题视频课' if is_zhuanti else '人教社官方视频课',
                })
        else:
            hint = near_miss_hint(ls['leaf_title'], ls['subject'], ls['grade'], topics_by_sg)
            rec = {k: ls[k] for k in ('book','subject','grade','ce','unit','lesson','leaf_title')}
            if hint:
                rec['near_miss_hint'] = hint
            unmatched_lessons.append(rec)

    # 按 topics.json 顺序输出
    order = {tp['id']: i for i, tp in enumerate(topics)}
    out = {'resources': [{'topicId': tid, 'items': resources[tid]} for tid in sorted(resources, key=order.get)]}
    with open(os.path.join(ROOT, 'data', 'resources_courses.json'), 'w', encoding='utf8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 报告
    target_topics = [tp for tp in topics if tp['subject'] in ('道德与法治', '语文')]
    covered = set(resources)
    uncovered = [{'id': tp['id'], 'subject': tp['subject'], 'grade': tp['gradeRangeStart'],
                  'domain': tp['domain'], 'name': tp['name']} for tp in target_topics if tp['id'] not in covered]
    by_sub = {}
    for tp in target_topics:
        d = by_sub.setdefault(tp['subject'], {'total': 0, 'covered': 0})
        d['total'] += 1
        d['covered'] += 1 if tp['id'] in covered else 0
    report = {
        'textbooks': [{'tmId': b[0], 'title': b[1], 'subject': b[2], 'grade': b[3], 'ce': b[4], 'edition': b[5]} for b in books],
        'lessons_total': len(all_lessons),
        'activities_total': sum(len(l['activities']) for l in all_lessons),
        'matched_lessons': len(matched_lessons),
        'match_levels': match_levels,
        'coverage_by_subject': by_sub,
        'topic_coverage': f"{len(covered)}/{len(target_topics)}",
        'uncovered_topics': uncovered,
        'unmatched_lessons': unmatched_lessons,
        'fetch_failures': failures,
        'match_detail': matched_lessons,
    }
    with open(os.path.join(ROOT, 'data', 'resources_courses_report.json'), 'w', encoding='utf8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print('\n== summary ==')
    print('lessons:', len(all_lessons), 'activities:', report['activities_total'])
    print('matched lessons:', len(matched_lessons), 'match levels:', match_levels)
    print('topic coverage:', report['topic_coverage'], by_sub)
    print('unmatched lessons:', len(unmatched_lessons))
    for x in unmatched_lessons[:15]:
        print('  miss:', x)

if __name__ == '__main__':
    main()
