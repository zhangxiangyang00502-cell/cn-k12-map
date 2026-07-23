#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_resources_pack.py — R5 资源管线扩展：把 resources.json 里已关联的
国家中小学智慧教育平台课时深链（syncClassroom/classActivity）扩展为
课程包"五件套"元数据：视频课程 / 课件 / 教学设计 / 学习任务单 / 课后练习。

数据源（免登录，已验证 HTTP 200）：
  课程包详情: https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/national_lesson/resources/details/{activityId}.json
    -> relations.national_course_resource[] 即五件套，字段含
       custom_properties.alias_name / format / size / duration / thumbnails
需要登录态（本脚本不硬爬，详见 scripts/README.md）：
  r*-ndr-private.ykt.cbern.com.cn 下的文件本体（mp4/m3u8/pdf/docx/pptx），
  无凭证直接访问返回 401。

产出: data/resources_pack.json，按 topicId 关联（与 resources.json 一致）。
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smartedu_lib import fetch_json  # 带磁盘缓存 + 限流 + 重试

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETAIL_API = ('https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/national_lesson'
              '/resources/details/{activity_id}.json')
# 精品课(elite_lesson)包在 national_lesson 详情接口返回 403，走通用资源接口
DETAIL_API_FALLBACK = 'https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/{activity_id}.json'

# alias_name -> (输出键, 中文类型名)
FIVE = {
    '视频课程': ('video', '视频课程'),
    '微课视频': ('video', '视频课程'),
    '课件': ('courseware', '课件'),
    '教学设计': ('lessonPlan', '教学设计'),
    '学习任务单': ('taskSheet', '学习任务单'),
    '课后练习': ('exercise', '课后练习'),
    '作业练习': ('exercise', '课后练习'),
}

DOC_EXT = re.compile(r'\.([a-z0-9]{2,5})(?:\?|$)', re.I)


def is_public(url):
    return url and '-private.' not in url


def pick_file(ti_items, prefer_flags=('href', 'pdf', 'source')):
    """从 ti_items 里挑主文件（直链）。返回 (url, sizeBytes, flag) 或 None。"""
    best = None
    for ti in ti_items or []:
        flag = ti.get('ti_file_flag') or ''
        urls = ti.get('ti_storages') or []
        if not urls:
            continue
        rank = prefer_flags.index(flag) if flag in prefer_flags else 99
        if best is None or rank < best[0]:
            best = (rank, urls[0], ti.get('ti_size'), flag)
    if best and best[0] < 99:
        return best[1], best[2], best[3]
    return None


def extract_piece(res):
    """从 relations 里的一条关联资源提取元数据。"""
    cp = res.get('custom_properties') or {}
    title = (res.get('global_title') or {}).get('zh-CN') or cp.get('original_title') or ''
    # 公开缩略图 / 预览图
    thumb = None
    for u in (cp.get('thumbnails') or []):
        if is_public(u):
            thumb = u
            break
    if not thumb:
        pv = cp.get('preview') or {}
        for k in sorted(pv):
            if is_public(pv[k]):
                thumb = pv[k]
                break
    # 主文件直链（通常需登录态）
    got = pick_file(res.get('ti_items'))
    file_url, file_size, file_flag = got if got else (None, None, None)
    fmt = cp.get('format')
    if not fmt and file_url:
        m = DOC_EXT.search(file_url)
        fmt = m.group(1).lower() if m else None
    # 课时标签（第一课时/第二课时…）
    lesson_tag = None
    for t in res.get('tag_list') or []:
        if t.get('tag_dimension_id') == 'bkks':
            lesson_tag = t.get('tag_name')
    return {
        'resourceId': res.get('id'),
        'title': title,
        'typeName': cp.get('alias_name') or res.get('resource_type_code_name'),
        'resourceType': res.get('resource_type_code'),
        'lessonTag': lesson_tag,
        'format': fmt,
        'sizeBytes': cp.get('size') or file_size,
        'duration': cp.get('duration'),          # ISO8601，如 PT22M4S，仅视频有
        'thumb': thumb,                           # 免登录可访问
        'downloadUrl': file_url,                  # 文件直链，多数需登录
        'requiresAuth': not is_public(file_url) if file_url else None,
    }


def extract_pack(detail):
    """从课程包详情 json 提取五件套。返回 {key: [pieces]} 与其他类型列表。"""
    rels = detail.get('relations') or {}
    rel = rels.get('national_course_resource') or rels.get('course_resource') or []
    pack = {k: [] for k, _ in FIVE.values()}
    others = []
    for r in rel:
        alias = (r.get('custom_properties') or {}).get('alias_name') or ''
        if alias in FIVE:
            pack[FIVE[alias][0]].append(extract_piece(r))
        else:
            others.append(alias or r.get('resource_type_code'))
    return pack, others


def main():
    src = json.load(open(os.path.join(ROOT, 'data', 'resources.json'), encoding='utf-8'))

    # 1) 收集 resources.json 中所有课时级深链 (topicId, activityId, ...)
    lessons = []
    seen_act = {}
    n_catalog_links = 0
    for r in src['resources']:
        for it in r['items']:
            if it.get('type') != 'course':
                continue
            u = it.get('url') or ''
            m = re.search(r'activityId=([0-9a-f-]{36})', u)
            if not m:
                if 'syncClassroom' in u:
                    n_catalog_links += 1
                continue
            act = m.group(1)
            ch = re.search(r'chapterId=([0-9a-f-]{36})', u)
            tm = re.search(r'teachingmaterialId=([0-9a-f-]{36})', u)
            lessons.append({
                'topicId': r['topicId'],
                'activityId': act,
                'chapterId': ch.group(1) if ch else None,
                'teachingmaterialId': tm.group(1) if tm else None,
                'playUrl': u,
                'courseTitle': it.get('title') or '',
            })
            seen_act[act] = None
    print(f'课时深链: {len(lessons)} 条, 去重活动: {len(seen_act)} 个, '
          f'跳过册级目录链接: {n_catalog_links} 条')

    # 2) 逐个拉课程包详情（带缓存；national_lesson 403 时回退通用资源接口）
    details = {}
    pkg_type = {}
    fails = []
    for i, act in enumerate(sorted(seen_act)):
        d = fetch_json(DETAIL_API.format(activity_id=act), f'detail_{act}.json')
        if d:
            details[act] = d
            pkg_type[act] = d.get('resource_type_code') or 'national_lesson'
        else:
            d = fetch_json(DETAIL_API_FALLBACK.format(activity_id=act),
                           f'detail_fallback_{act}.json')
            if d:
                details[act] = d
                pkg_type[act] = d.get('resource_type_code') or 'elite_lesson'
            else:
                fails.append(act)
        if (i + 1) % 20 == 0:
            print(f'  details {i + 1}/{len(seen_act)}')

    # 3) 组装 resources_pack.json
    packs = {}
    stat_types = {k: 0 for k, _ in FIVE.values()}
    stat_pieces = 0
    incomplete = []   # 缺件的课程包
    for ls in lessons:
        d = details.get(ls['activityId'])
        if not d:
            continue
        pack, others = extract_pack(d)
        lesson_title = (d.get('global_title') or {}).get('zh-CN') or d.get('title') or ''
        pt = pkg_type.get(ls['activityId'], '')
        missing = [cn for k, cn in FIVE.values() if not pack[k]]
        missing = sorted(set(missing))
        if missing:
            incomplete.append({'activityId': ls['activityId'], 'title': lesson_title,
                               'packageType': pt, 'missing': missing,
                               'other_types': others})
        for k in pack:
            stat_types[k] += len(pack[k])
            stat_pieces += len(pack[k])
        entry = {
            'activityId': ls['activityId'],
            'chapterId': ls['chapterId'],
            'teachingmaterialId': ls['teachingmaterialId'],
            'packageType': pt,
            'lessonTitle': lesson_title,
            'playUrl': ls['playUrl'],
            'source': '国家中小学智慧教育平台',
            'pack': pack,
        }
        packs.setdefault(ls['topicId'], []).append(entry)

    # 按 resources.json 的 topicId 顺序输出
    order = [r['topicId'] for r in src['resources']]
    out = {
        'meta': {
            'source': '国家中小学智慧教育平台 (basic.smartedu.cn) national_lesson/elite_lesson 课程包',
            'detailApi': DETAIL_API,
            'detailApiFallback': DETAIL_API_FALLBACK,
            'note': 'thumb 免登录可访问；downloadUrl 指向 r*-ndr-private 域，'
                    '无登录凭证返回 401，需在平台登录后使用。五件套均可在 playUrl 页内查看。',
            'stats': {
                'lesson_links': len(lessons),
                'unique_activities': len(seen_act),
                'details_fetched': len(details),
                'details_failed': fails,
                'topics_covered': len(packs),
                'pieces_total': stat_pieces,
                'pieces_by_type': stat_types,
                'catalog_links_skipped': n_catalog_links,
                'incomplete_packs': len(incomplete),
            },
        },
        'packs': [{'topicId': tid, 'items': packs[tid]}
                  for tid in order if tid in packs],
    }
    # 缺件明细附在 meta 后，便于后续补抓
    out['meta']['incomplete_detail'] = incomplete

    dst = os.path.join(ROOT, 'data', 'resources_pack.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'\n写出 {dst}')
    print('覆盖知识点:', len(packs), ' 五件套条目:', stat_pieces, stat_types)
    print('详情拉取失败:', fails)
    print('缺件课程包:', len(incomplete))
    for x in incomplete[:10]:
        print('  缺', x['missing'], '|', x['title'], x['other_types'])


if __name__ == '__main__':
    main()
