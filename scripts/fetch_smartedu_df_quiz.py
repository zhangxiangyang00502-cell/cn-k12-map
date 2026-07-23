#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从国家中小学智慧教育平台题库抓取道德与法治官方单选题，匹配 topics.json 节点。

用法:
  python3 scripts/fetch_smartedu_df_quiz.py match   # 只做节点->课时匹配，打印映射表
  python3 scripts/fetch_smartedu_df_quiz.py run     # 全量抓取并写 data/quiz_official_df.json + report
"""
import json, os, re, sys, time, html, difflib, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw_smartedu')
os.makedirs(RAW, exist_ok=True)

BOOKS = {  # grade -> [(book_label, tmId)]
    7: [('七上', 'd350d7ac-8166-4b30-88d4-1fe48457f8e8'),
        ('七下', '0950ee38-88ea-4da9-8da9-bafb9dade3e1'),
        ('七上旧', 'be1c9d29-3544-4687-9afa-2aa7cb45b4b6')],
    8: [('八上', 'a7269cde-d3a4-452b-8013-2e3a44d4382e'),
        ('八下', '02d175b7-a0d7-4ae2-8e52-d946bf8f73f4'),
        ('八上旧', '955fadcc-fb53-4225-b4d9-af191d7a1553'),
        ('八下旧', '998d1fd7-8912-48ed-affd-4242ced28894')],
    9: [('九上', '399e395b-ed98-44b2-903f-39f41f26a548'),
        ('九下', 'bec0aa15-d286-4f1b-98cc-143b91c00af5')],
}

# 人工核对的补充映射: topic_id -> (tmId, [课时标题...])
X7S = 'd350d7ac-8166-4b30-88d4-1fe48457f8e8'   # 新七上
X7X = '0950ee38-88ea-4da9-8da9-bafb9dade3e1'   # 新七下
O7S = 'be1c9d29-3544-4687-9afa-2aa7cb45b4b6'   # 旧七上
X8S = 'a7269cde-d3a4-452b-8013-2e3a44d4382e'   # 新八上
X8X = '02d175b7-a0d7-4ae2-8e52-d946bf8f73f4'   # 新八下
O8S = '955fadcc-fb53-4225-b4d9-af191d7a1553'   # 旧八上
O8X = '998d1fd7-8912-48ed-affd-4242ced28894'   # 旧八下
O9S = '399e395b-ed98-44b2-903f-39f41f26a548'   # 旧九上
O9X = 'bec0aa15-d286-4f1b-98cc-143b91c00af5'   # 旧九下
MANUAL = {
    'cn_df_zjsh_01': (O8S, ['我与社会']),                     # 认识社会生活
    'cn_df_zjsh_03': (O8S, ['在社会中成长']),                 # 人的社会化
    'cn_df_zjsh_06': (O8S, ['合理利用网络']),                 # 营造清朗网络空间
    'cn_df_czsk_02': (X7S, ['让家更美好']),                   # 建设幸福和睦的家庭
    'cn_df_ccwh_02': (X7X, ['做核心思想理念的传承者']),        # 传承核心思想理念的当代价值
    'cn_df_ccwh_03': (X7X, ['影响深远的人文精神']),            # 感悟中华人文精神
    'cn_df_whzx_02': (O8S, ['遵守规则']),                     # 自觉遵守与维护规则
    'cn_df_whzx_03': (O8S, ['尊重他人', '以礼待人']),          # 尊重他人 以礼待人
    'cn_df_whzx_07': (O8S, ['善用法律']),                     # 学会依法办事
    'cn_df_ydzr_01': (O8X, ['自由平等的真谛']),               # 珍视自由
    'cn_df_ydzr_02': (O8X, ['自由平等的追求']),               # 践行平等
    'cn_df_ydzr_03': (O8X, ['公平正义的价值']),
    'cn_df_ydzr_04': (O8X, ['公平正义的守护']),               # 守护公平正义
    'cn_df_ydzr_05': (O8S, ['关爱他人']),
    'cn_df_ydzr_06': (O8S, ['服务社会']),                     # 服务奉献社会
    'cn_df_whgy_01': (O8S, ['国家好 大家才会好']),             # 国家利益与人民利益
    'cn_df_xfzs_01': (O8X, ['党的主张和人民意志的统一']),      # 党领导人民制定宪法
    'cn_df_xfzs_05': (O8X, ['加强宪法监督']),
    'cn_df_gjzd_01': (O8X, ['根本政治制度']),                 # 人民代表大会制度
    'cn_df_gjzd_02': (O8X, ['基本政治制度']),                 # 多党合作和政治协商制度
    'cn_df_gjzd_03': (X8X, ['民族区域自治制度', '基层群众自治制度']),
    'cn_df_fzgg_05': (O9S, ['凝聚法治共识']),                 # 厉行法治 全民守法
    'cn_df_gyzgm_01': (O9S, ['促进民族团结']),                # 铸牢中华民族共同体意识
    'cn_df_gyzgm_02': (O9S, ['维护祖国统一']),                # 实现祖国完全统一
    'cn_df_gyzgm_03': (O9S, ['我们的梦想']),                  # 民族复兴梦
    'cn_df_gyzgm_04': (O9S, ['共圆中国梦']),                  # 我们都是追梦人
    'cn_df_wmdsjj_03': (O9X, ['推动和平与发展']),             # 和平与发展是时代主题
    'cn_df_sjwt_04': (O9X, ['与世界深度互动']),               # 文明交流互鉴（该课内含）
    'cn_df_sjwt_05': (O9X, ['中国的机遇与挑战']),             # 新机遇与新挑战
    'cn_df_zxwl_01': (O9X, ['少年当自强']),                   # 少年强则国强
    'cn_df_zxwl_02': (O9X, ['走向世界大舞台']),               # 为世界添光彩
    'cn_df_zxwl_04': (O9X, ['学无止境']),                     # 在实践中学习
    'cn_df_zxwl_05': (O9X, ['走向未来']),                     # 畅想未来 规划人生
}

MAX_PER_TOPIC = 8
MAX_STEM_LEN = 300

# ---------- HTTP with cache ----------
def fetch_json(url, cache_path, retries=3):
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding='utf-8') as f:
            return json.load(f)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            if cache_path:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
            time.sleep(0.2)
            return data
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last

# ---------- text utils ----------
TAG_RE = re.compile(r'<[^>]+>')
def strip_html(s):
    if not s:
        return ''
    s = TAG_RE.sub('', s)
    s = html.unescape(s).replace('\xa0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()

def norm(s):
    """标题归一化：去空白、标点、全角差异"""
    if not s:
        return ''
    s = html.unescape(str(s))
    s = re.sub(r'[\s　]+', '', s)
    s = re.sub(r'[：:，,。、；;！!？?（）()《》〈〉“”"\'‘’·\-—…~～]', '', s)
    return s

def clean_stem(q):
    q = re.sub(r'^\s*\d+\s*[.、．]\s*', '', q)
    q = re.sub(r'^（(?:改编|原创|中考真题|模拟)）\s*', '', q)
    return q.strip()

# ---------- tree parsing ----------
def load_tree(tm):
    fn = os.path.join(RAW, 'trees', f'{tm}.json')
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    return fetch_json(f'https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/trees/{tm}.json', fn)

def parse_tree(tree):
    """返回 (leaves, middles): leaves=[{id,title,unit,ke}], middles=[{id,title,unit,leaf_ids,leaf_titles}]"""
    roots = tree if isinstance(tree, list) else tree.get('child_nodes', [])
    leaves, middles = [], []
    for unit in roots:
        unit_title = (unit.get('title') or '').strip()
        for ke in (unit.get('child_nodes') or []):
            ke_title = (ke.get('title') or '').strip()
            kids = ke.get('child_nodes') or []
            real = [k for k in kids if (k.get('title') or '').strip() and '单元思考' not in k.get('title')]
            if real:
                middles.append({'id': ke.get('id'), 'title': ke_title, 'unit': unit_title,
                                'leaf_ids': [k['id'] for k in real],
                                'leaf_titles': [(k.get('title') or '').strip() for k in real]})
                for k in real:
                    leaves.append({'id': k['id'], 'title': (k.get('title') or '').strip(),
                                   'unit': unit_title, 'ke': ke_title})
    return leaves, middles

# ---------- question index ----------
def load_question_index(tm):
    parts = fetch_json(
        f'https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/questions/teachingmaterials/{tm}/national_resources/parts.json',
        os.path.join(RAW, 'qidx', f'{tm}_parts.json'))
    out = []
    for u in parts:
        fn = os.path.join(RAW, 'qidx', f"{tm}_{u.split('/')[-1]}")
        out.extend(fetch_json(u, fn))
    return out

def is_single_choice(entry):
    names = {t.get('tag_name') for t in entry.get('tag_list', [])}
    return '单选题' in names

# ---------- matching ----------
def match_topics(topics, book_data, leaf_qcount=None):
    """book_data: tm -> (label, leaves, middles); leaf_qcount: leaf_id -> 单选题数。
    返回 mapping topic_id -> (tm, [leaf_id...], how, note)"""
    leaf_qcount = leaf_qcount or {}
    mapping, unmatched = {}, []
    for t in topics:
        grade = t['gradeRangeStart']
        name, domain = t['name'], t['domain']
        if t['id'] in MANUAL:
            tm, titles = MANUAL[t['id']]
            label, leaves, middles = book_data[tm]
            ids = [l['id'] for l in leaves if l['title'] in titles]
            if ids:
                mapping[t['id']] = (tm, ids, 'manual', f'{label}:{"|".join(titles)}')
            else:
                unmatched.append((t, f'人工映射的课时不存在: {titles}'))
            continue
        cand = []  # (score, tm, leaf_ids, how, desc)
        for tm in [tm for g, books in BOOKS.items() if g == grade for _, tm in books]:
            label, leaves, middles = book_data[tm]
            nn, nd = norm(name), norm(domain)
            # rule 1/2/3: leaf 级匹配
            for l in leaves:
                nl = norm(l['title'])
                if not nl:
                    continue
                same_unit = (nd and nd in norm(l['unit'])) or (norm(l['unit']) and norm(l['unit']) in nd)
                base = name.split('：')[0].split(':')[0]
                nb = norm(base)
                score = 0
                if nl == nn:
                    score = 100
                elif nb and nl == nb:
                    score = 95
                elif len(nl) >= 4 and (nl in nn or nn in nl):
                    score = 90
                else:
                    r = difflib.SequenceMatcher(None, nl, nn).ratio()
                    if r >= 0.75:
                        score = int(r * 80)
                if score:
                    if same_unit:
                        score += 5
                    if leaf_qcount.get(l['id']):
                        score += 20  # 优先选择题库里真正有题的教材（新教材部分册题库为空）
                    cand.append((score, tm, [l['id']], 'leaf', f"{label}:{l['title']}"))
            # rule 4: 课(中间层)匹配 → 全部叶子
            for m in middles:
                mk = norm(re.sub(r'^第[一二三四五六七八九十百\d]+课\s*', '', m['title']))
                if not mk:
                    continue
                score = 0
                if mk == nn:
                    score = 93
                elif len(mk) >= 4 and (mk in nn or nn in mk):
                    score = 88
                if score:
                    if nd and nd in norm(m['unit']):
                        score += 5
                    cand.append((score, tm, m['leaf_ids'], 'ke', f"{label}:{m['title']}→{'|'.join(m['leaf_titles'])}"))
        if cand:
            cand.sort(key=lambda x: -x[0])
            s, tm, ids, how, desc = cand[0]
            mapping[t['id']] = (tm, ids, how + f'@{s}', desc)
        else:
            unmatched.append((t, '题库的对应教材中无同名/近似课时'))
    return mapping, unmatched

# ---------- question detail -> quiz ----------
def fetch_detail(entry):
    cid, qid = entry['container_id'], entry['id']
    fn = os.path.join(RAW, 'qdetail', f'{qid}.json')
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    hosts = ['bdcs-file-1.ykt.cbern.com.cn', 's-file-1.ykt.cbern.com.cn', 's-file-2.ykt.cbern.com.cn']
    last = None
    for h in hosts:
        try:
            return fetch_json(f'https://{h}/zxx/api_static/questions/{cid}_{qid}/data.json', fn)
        except Exception as e:
            last = e
    raise last

def to_quiz(det):
    """返回 dict 或 (None, reason)"""
    c = det.get('content') or {}
    raw_q = c.get('description') or c.get('title') or ''
    items = c.get('items') or []
    if not items:
        return None, '无选项结构'
    ch = items[0].get('choices') or []
    if len(ch) < 2:
        return None, '选项少于2个'
    blob = raw_q + ''.join(x.get('text') or '' for x in ch)
    if re.search(r'<img|<table|\$\{ref-path\}', blob, re.I):
        return None, '含图片/表格'
    answers = []
    for r in c.get('responses') or []:
        if r.get('cardinality') != 'single':
            return None, '非单选'
        answers.extend(r.get('corrects') or [])
    answers = [a for a in answers if a in 'ABCDEFGH']
    if len(answers) != 1:
        return None, '答案不唯一或缺失'
    letters = [x.get('identifier') for x in ch]
    if answers[0] not in letters:
        return None, '答案不在选项中'
    q = clean_stem(strip_html(raw_q))
    if not q or len(q) > MAX_STEM_LEN:
        return None, f'题干为空或超长({len(q)})'
    options = []
    for x in ch:
        txt = strip_html(x.get('text') or '')
        if not txt:
            return None, '选项为空'
        options.append(f"{x['identifier']}. {txt}")
    fb = c.get('feedbacks') or []
    exp_raw = ''
    for f in fb:
        if f.get('identifier') == 'showAnswer':
            exp_raw = f.get('content') or ''
            break
    if not exp_raw and fb:
        exp_raw = fb[-1].get('content') or ''
    explain = strip_html(exp_raw)
    return {'type': 'choice', 'q': q, 'options': options,
            'answer': answers[0], 'explain': explain}, None

# ---------- main ----------
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'match'
    topics = json.load(open(os.path.join(ROOT, 'data', 'topics.json'), encoding='utf-8'))['topics']
    df = [t for t in topics if t['subject'] == '道德与法治']

    book_data = {}
    qidx = {}   # leaf_id -> [entry]
    for grade, books in BOOKS.items():
        for label, tm in books:
            leaves, middles = parse_tree(load_tree(tm))
            book_data[tm] = (label, leaves, middles)
            for e in load_question_index(tm):
                if not is_single_choice(e):
                    continue
                chs = e.get('chapter_ids') or []
                if chs:
                    qidx.setdefault(chs[-1], []).append(e)
    leaf_qcount = {lid: len(es) for lid, es in qidx.items()}

    mapping, unmatched = match_topics(df, book_data, leaf_qcount)

    if mode == 'match':
        for t in df:
            if t['id'] in mapping:
                tm, ids, how, desc = mapping[t['id']]
                print(f"[OK] {t['id']} {t['gradeRangeStart']}年级 {t['name']}  ->  {desc}  ({how})")
            else:
                reason = next(r for x, r in unmatched if x['id'] == t['id'])
                print(f"[--] {t['id']} {t['gradeRangeStart']}年级 {t['domain']}|{t['name']}  ({reason})")
        print(f"\n匹配 {len(mapping)}/{len(df)}")
        return

    # run 模式：抓取题目
    questions, per_topic, reasons = [], {}, {}
    used_qids = set()  # 全局去重：一道题只归属一个节点
    for t in df:
        tid = t['id']
        if tid not in mapping:
            per_topic[tid] = 0
            reasons[tid] = next(r for x, r in unmatched if x['id'] == tid)
            continue
        tm, leaf_ids, how, desc = mapping[tid]
        entries = []
        for lid in leaf_ids:
            entries.extend(qidx.get(lid, []))
        got, seen = [], set()
        skip = {}
        for e in entries:
            if len(got) >= MAX_PER_TOPIC:
                break
            if e['id'] in used_qids:
                continue
            try:
                det = fetch_detail(e)
            except Exception as ex:
                skip['详情下载失败'] = skip.get('详情下载失败', 0) + 1
                continue
            quiz, why = to_quiz(det)
            if not quiz:
                skip[why] = skip.get(why, 0) + 1
                continue
            key = norm(quiz['q'])
            if key in seen:
                skip['重复题干'] = skip.get('重复题干', 0) + 1
                continue
            seen.add(key)
            used_qids.add(e['id'])
            quiz['topicId'] = tid
            got.append(quiz)
        questions.extend(got)
        per_topic[tid] = len(got)
        if not got:
            reasons[tid] = '课时下无可用单选题' + (f'（跳过: {skip}）' if skip else '')

    out = {'questions': questions}
    with open(os.path.join(ROOT, 'data', 'quiz_official_df.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    tm2label = {tm: label for _, books in BOOKS.items() for label, tm in books}
    report = {
        'source': '国家中小学智慧教育平台 题库（basic.smartedu.cn）',
        'books': {tm2label[tm]: tm for tm in tm2label},
        'total_questions': len(questions),
        'topics_expected': len(df),
        'topics_covered': sum(1 for v in per_topic.values() if v > 0),
        'per_book': {},
        'per_topic': [],
        'unmatched': [{'topicId': x['id'], 'grade': x['gradeRangeStart'],
                       'domain': x['domain'], 'name': x['name'], 'reason': r} for x, r in unmatched],
        'no_questions': [{'topicId': tid, 'reason': reasons[tid]}
                         for tid in per_topic if per_topic[tid] == 0 and tid not in {x['id'] for x, _ in unmatched}],
    }
    for t in df:
        entry = {'topicId': t['id'], 'grade': t['gradeRangeStart'], 'domain': t['domain'],
                 'name': t['name'], 'count': per_topic[t['id']]}
        if t['id'] in mapping:
            tm, ids, how, desc = mapping[t['id']]
            entry['matched'] = desc
            entry['match_type'] = how
        report['per_topic'].append(entry)
        label = desc.split(':')[0] if t['id'] in mapping else ('七上/七下' if t['gradeRangeStart'] == 7 else '八上/八下' if t['gradeRangeStart'] == 8 else '九上/九下')
        for lb in label.split('/'):
            b = report['per_book'].setdefault(lb, {'topics': 0, 'covered': 0, 'questions': 0})
            b['topics'] += 1
            if per_topic[t['id']] > 0:
                b['covered'] += 1
            b['questions'] += per_topic[t['id']]
    with open(os.path.join(ROOT, 'data', 'quiz_official_df_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"总题数 {len(questions)}, 覆盖 {report['topics_covered']}/{len(df)}")

if __name__ == '__main__':
    main()
