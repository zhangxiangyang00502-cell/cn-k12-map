# 合并：用 2024 版统编教材道法 + K12 全学段语文 替换旧数据
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_df7 import DF7, DF7_SKIP
from gen_df8 import DF8, DF8_SKIP
from gen_df9 import DF9, DF9_SKIP, DF_CROSS
from gen_yw1 import YW1
from gen_yw2 import YW2
from gen_yw_edges import YW_SKIP, YW_CROSS

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def load(n): return json.load(open(os.path.join(ROOT, 'data', n), encoding='utf-8'))
def save(n, obj):
    with open(os.path.join(ROOT, 'data', n), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write('\n')

topics = load('topics.json')['topics']
deps = load('dependencies.json')['dependencies']
clusters = load('clusters.json')['clusters']
curricula = load('curriculum-standards.json')['curricula']

# ---------- 1. 新道法节点 ----------
GRADE_OF = {'7上': 7, '7下': 7, '8上': 8, '8下': 8, '9上': 9, '9下': 9}
df_nodes, df_edges = [], []
for df_units in (DF7, DF8, DF9):
    for domain, band, nodes in df_units:
        g = GRADE_OF[band]
        prev = None
        for (suf, typ, name, desc, ev, prompt, stds, pre) in nodes:
            df_nodes.append({
                "id": f"cn_df_{suf}", "type": typ, "subject": "道德与法治",
                "domain": domain, "name": name, "description": desc,
                "gradeRangeStart": g, "gradeRangeEnd": g, "status": "complete",
                "evidence": ev, "assessmentPrompt": prompt, "standards": stds,
            })
            if prev and pre:
                df_edges.append({"topicId": f"cn_df_{suf}", "prerequisiteId": f"cn_df_{prev}",
                                 "strength": "hard", "reason": pre})
            prev = suf
for lst in (DF7_SKIP, DF8_SKIP, DF9_SKIP, DF_CROSS):
    for (t, p, s, r) in lst:
        df_edges.append({"topicId": f"cn_df_{t}", "prerequisiteId": f"cn_df_{p}",
                         "strength": s, "reason": r})

# ---------- 2. 新语文节点 ----------
yw_nodes, yw_edges = [], []
for yw_units in (YW1, YW2):
    for domain, band, nodes in yw_units:
        prev = None
        for (suf, typ, name, gs, ge, desc, ev, prompt, stds, pre) in nodes:
            yw_nodes.append({
                "id": f"cn_yw_{suf}", "type": typ, "subject": "语文",
                "domain": domain, "name": name, "description": desc,
                "gradeRangeStart": gs, "gradeRangeEnd": ge, "status": "complete",
                "evidence": ev, "assessmentPrompt": prompt, "standards": stds,
            })
            if prev and pre:
                yw_edges.append({"topicId": f"cn_yw_{suf}", "prerequisiteId": f"cn_yw_{prev}",
                                 "strength": "hard", "reason": pre})
            prev = suf
for lst in (YW_SKIP, YW_CROSS):
    for (t, p, s, r) in lst:
        yw_edges.append({"topicId": f"cn_yw_{t}", "prerequisiteId": f"cn_yw_{p}",
                         "strength": s, "reason": r})

# 去重 + 自环检查
def dedup(edges):
    seen, out = set(), []
    for e in edges:
        k = (e['topicId'], e['prerequisiteId'])
        if k in seen or e['topicId'] == e['prerequisiteId']:
            continue
        seen.add(k); out.append(e)
    return out
df_edges, yw_edges = dedup(df_edges), dedup(yw_edges)
new_ids = {n['id'] for n in df_nodes + yw_nodes}
for e in df_edges + yw_edges:
    assert e['topicId'] in new_ids and e['prerequisiteId'] in new_ids, e

# ---------- 3. 合并 topics / dependencies ----------
drop_subjects = {'道德与法治', '语文'}
old_keep = [t for t in topics if t['subject'] not in drop_subjects]
old_ids = {t['id'] for t in old_keep}
deps_keep = [d for d in deps if d['topicId'] in old_ids and d['prerequisiteId'] in old_ids]

new_topics = df_nodes + old_keep[:0] + yw_nodes  # 顺序：道法、（其余保持原序）、语文
# 保持原有整体顺序：非法非语文学科原序，道法与语文按新内容放在头部？改为：先其余学科原序，再把道法、语文追加以保持其余不动
new_topics = old_keep + df_nodes + yw_nodes
new_deps = deps_keep + df_edges + yw_edges
save('topics.json', {"topics": new_topics})
save('dependencies.json', {"dependencies": new_deps})

# ---------- 4. 课标：追加语文 slug ----------
yw_std = {
 "slug": "yw-yuwen-2022",
 "name": "义务教育语文课程标准（2022年版）· 普通高中语文课程标准（2017年版2020年修订）",
 "standards": [
  {"key": "yw-yuwen-2022:语文.识字与写字.第一学段",
   "title": "识字与写字（第一学段 1-2年级）",
   "summary": "喜欢学习汉字，有主动识字、写字的愿望；认识常用汉字1600个左右、会写800个左右；掌握汉语拼音，学会音序查字法和部首查字法；写字姿势正确，书写规范、端正、整洁。"},
  {"key": "yw-yuwen-2022:语文.识字与写字.第二三学段",
   "title": "识字与写字（第二、三学段 3-6年级）",
   "summary": "累计认识常用汉字3000个左右、会写2500个左右；能熟练使用字典词典独立识字；硬笔书写正楷行款整齐、有一定速度，学写毛笔字，感受汉字文化内涵。"},
  {"key": "yw-yuwen-2022:语文.语言文字积累与梳理.义务教育",
   "title": "语言文字积累与梳理（基础型任务群）",
   "summary": "在真实的语言运用情境中积累语言材料和语言经验：字词句篇、修辞语法、文言词汇、文化常识；通过梳理与探究发现语言文字的运用规律，奠定语文基础。"},
  {"key": "yw-yuwen-2022:语文.实用性阅读与交流.第一二学段",
   "title": "实用性阅读与交流（第一、二学段）",
   "summary": "学习朗读与默读，借助关键词句理解内容；阅读说明性、叙事性浅近文本，学习提取信息；学写留言条、请假条等简单应用文，乐于口头交流。"},
  {"key": "yw-yuwen-2022:语文.实用性阅读与交流.第三四学段",
   "title": "实用性阅读与交流（第三、四学段）",
   "summary": "阅读说明性文章、非连续性文本和新闻，抓住要点、了解说明方法；学写说明介绍、倡议书、调查报告等实用文；在讨论、演讲、辩论中清楚得体地表达与交流。"},
  {"key": "yw-yuwen-2022:语文.文学阅读与创意表达.第一二学段",
   "title": "文学阅读与创意表达（第一、二学段）",
   "summary": "诵读儿歌、儿童诗和浅近古诗，展开想象获得初步情感体验；阅读童话、寓言、故事，关心人物命运；对写话有兴趣，学习写见闻和想象，尝试写片段。"},
  {"key": "yw-yuwen-2022:语文.文学阅读与创意表达.第三四学段",
   "title": "文学阅读与创意表达（第三、四学段）",
   "summary": "阅读叙事性作品、散文、小说、诗词和浅易文言文，把握内容、人物形象与表达手法，有自己的情感体验；学习写记叙文，内容具体、感情真实，学习修改习作。"},
  {"key": "yw-yuwen-2022:语文.思辨性阅读与表达.第三四学段",
   "title": "思辨性阅读与表达（第三、四学段）",
   "summary": "阅读思辨性文本，区分事实与观点，把握论点、论据与论证方法，分析论证思路；学习写简单的议论性文章和时事短评，做到观点明确、有理有据、表达有逻辑。"},
  {"key": "yw-yuwen-2022:语文.整本书阅读.义务教育",
   "title": "整本书阅读（拓展型任务群）",
   "summary": "每学年阅读两三部名著，义务教育阶段课外阅读总量不少于400万字；学习圈点批注、做读书笔记、画思维导图，分享阅读心得，养成良好的阅读习惯。"},
  {"key": "yw-yuwen-2022:语文.跨学科学习.义务教育",
   "title": "跨学科学习（拓展型任务群）",
   "summary": "围绕学科学习和社会生活中的话题开展探究活动：搜集整理资料、调查研究、策划活动、撰写报告，在跨学科、跨媒介的真实情境中综合运用语文能力。"},
  {"key": "yw-yuwen-2022:语文.高中.整本书阅读与研讨",
   "title": "高中：整本书阅读与研讨",
   "summary": "在指定范围内阅读一部长篇小说（如《红楼梦》）和一部学术著作（如《乡土中国》），把握艺术架构或概念体系，开展专题研讨，撰写读书笔记与研究报告。"},
  {"key": "yw-yuwen-2022:语文.高中.思辨性阅读与表达及文学阅读与写作",
   "title": "高中：思辨性阅读与表达 / 文学阅读与写作",
   "summary": "阅读论述类与学术类文本，把握概念、判断与推理，发展实证、推理与批判能力，写作观点深刻、论证严密的议论文；鉴赏古今中外文学作品，写作文学短评与文学性文章，提升审美鉴赏与创造能力。"},
 ]}
curricula = [c for c in curricula if c['slug'] != 'yw-yuwen-2022'] + [yw_std]
save('curriculum-standards.json', {"curricula": curricula})

# ---------- 5. clusters ----------
DF_CLUSTER_SUM = {
 "少年有梦": ("7上", "孩子刚上初中，这一单元帮他接住新起点：规划初中生活、正确认识自己、种下梦想的种子，并明白学习是梦想的桥。家长少问分数，多问'你这个月的小目标是什么'。"),
 "成长的时空": ("7上", "这一单元讲孩子最重要的三个关系场：家庭、师生、友谊与集体。重点是建设和睦家庭、珍惜师生情谊、学会交友与呵护友谊、在集体中涵养品格。"),
 "珍爱我们的生命": ("7上", "从认识生命、敬畏生命，到增强安全意识、提高防护能力，再到爱护身体、滋养心灵——新教材把'生命教育'做成完整体系，家长可以和孩子做一次家庭安全演练。"),
 "追求美好人生": ("7上", "七上收官单元：确立人生目标、以积极态度对待顺境逆境、在劳动与奉献中创造价值。帮孩子把大目标拆成这学期能做到的三件小事。"),
 "珍惜青春时光": ("7下", "直面青春期：身心变化、异性交往、自我保护，再到情绪管理与美好情感。这一阶段孩子需要的不是说教，而是可以商量的父母。"),
 "焕发青春活力": ("7下", "自尊、自信、自强三部曲，最后落到'做自强不息的中国人'。多给孩子创造成就体验，实力是自信的支柱。"),
 "传承中华优秀传统文化": ("7下", "从历久弥新的思想理念，到中华人文精神、传统美德，最后落到文化自信。家长可以和孩子一起过节、读经典、聊家风，让传统活在日常里。"),
 "生活在法治社会": ("7下", "法治启蒙：法律体系、民法典、人身权与财产权、违法与犯罪。关键是让孩子知道法律既保护他、也约束他，年龄不是护身符。"),
 "走进社会生活": ("8上", "从'我与社会'到社会化、亲社会行为，再到网络生活新空间。鼓励孩子参加社会实践，也和他一起立一份家庭网络使用公约。"),
 "维护社会秩序": ("8上", "规则、道德、法治三条线：自觉遵守规则、尊重诚信友善、树立法治观念、学会依法办事。遇事问孩子一句'按规则该怎么办'。"),
 "勇担社会责任": ("8上", "自由平等、公平正义、关爱他人、奉献社会。新教材把原八下的自由平等前移到这里，逻辑是'社会价值→个人担当'。"),
 "维护国家利益": ("8上", "国家利益至上、军强才能国安、总体国家安全观。结合时事和孩子聊聊：国家安全不只是抓间谍，粮食、网络、生态都是。"),
 "坚持宪法至上": ("8下", "宪法专册开篇：党领导人民制定宪法、宪法的内容与最高效力、依宪治国与宪法监督。12月4日国家宪法日可以和孩子一起读宪法。"),
 "理解权利义务": ("8下", "公民基本权利与义务、权利义务相统一、依法行使权利、依法履行义务。网购维权、网络发言都是现成的教学情境。"),
 "认识国家制度": ("8下", "政治制度（人大制度、政党制度、民族区域自治与基层自治）+ 经济制度（所有制、分配、市场经济）。用身边例子讲抽象制度。"),
 "走近国家机构": ("8下", "人大、国家主席、政府、军委、监委、法院检察院逐个认识。看新闻联播时帮孩子指出'这是哪个机关在行使什么职权'。"),
 "建设法治中国": ("8下", "全面依法治国：指导思想、总目标、法治与改革、法治与德治、全民守法。八年级法治教育的收束，为九年级国情学习奠基。"),
 "坚持党的全面领导": ("9上", "九上开篇：百年恢宏史诗、伟大建党精神、初心使命、人民立场、坚强的领导核心。这是新教材把'党的领导'独立成单元的重大调整。"),
 "进入新时代": ("9上", "社会主要矛盾变化、新时代的意义、思想旗帜，以及经济、政治、文化、民生、生态五大领域的成就。用家庭账本和家乡变化讲'新时代'。"),
 "奋进新征程": ("9上", "'两步走'战略、中国式现代化、新发展理念、新发展格局、高质量发展。让孩子算算 2035 和 2050 年自己多大——他是建设者。"),
 "共圆中国梦": ("9上", "民族团结、祖国统一、中国梦与追梦人、自信的中国人。九上收官，落到'我能为圆梦做什么'。"),
 "我们共同的世界": ("9下", "（课标推导，目录待核对）开放互动的世界、复杂国际关系、和平与发展、人类命运共同体。九下预计 2027 春启用新教材，目前按 2022 课标国情教育主题组织。"),
 "世界舞台上的中国": ("9下", "（课标推导，目录待核对）中国担当、中国智慧中国方案、与世界的深度互动、文明互鉴、新机遇新挑战。新教材出版后需按实际目录校准。"),
 "走向未来的少年": ("9下", "（课标推导，目录待核对）少年强则国强、为世界添光彩、职业选择、在实践中学习、规划人生——义务教育收官，把个人未来接上国家未来。"),
}
YW_CLUSTER_SUM = {
 "汉语拼音与识字写字": ("1-6年级", "语文的地基工程：拼音是拐杖，识字量按 1600→2500→3000 三级跳，写字从姿势、笔顺到间架结构、毛笔临摹。低年级抓习惯，中高年级抓纠错与规范。"),
 "语言文字积累与梳理": ("1-9年级", "语文的'仓库管理员'：词语成语、标点关联词、修辞语法、文言实词虚词、文化常识，先积累后梳理，把语感变成规律。摘抄本和错字本是最实用的两件工具。"),
 "实用性阅读与交流": ("1-12年级", "应对真实世界的语文：朗读默读、概括信息、说明文与非连续性文本、新闻与演讲、应用文与调查报告，高中接入学术阅读与情境写作。核心是'读得懂信息，办得成事情'。"),
 "文学阅读与创意表达": ("1-12年级", "语文最富诗意的主线：儿歌童话→记叙文读写→散文小说诗词文言→高中的深度鉴赏与文学短评。写作线同步进阶：写话→片段→完整记叙文→文学化表达。"),
 "思辨性阅读与表达": ("3-12年级", "从'大胆提问'到'论证严密'：小学区分事实与观点，初中吃透议论文三要素与写法，高中攻逻辑推理、谬误识别与辩证分析。信息时代最防身的一条线。"),
 "整本书阅读": ("1-12年级", "从绘本桥梁书到《红楼梦》《乡土中国》：计划、批注、思维导图三大方法贯穿，名著阅读螺旋上升。家里最重要的是固定的阅读时间和聊书的餐桌。"),
 "跨学科学习": ("3-12年级", "把语文用出去：资料搜集、调查研究、活动策划、专题探究、成果发布，在真实任务中综合调用听说读写。项目不在大，真问题真成果最重要。"),
}
new_clusters = [c for c in clusters if c['subject'] not in {'道德与法治', '语文'}]
for df_units in (DF7, DF8, DF9):
    for domain, band, _ in df_units:
        summ = DF_CLUSTER_SUM[domain][1]
        new_clusters.append({"subject": "道德与法治", "domain": domain,
                             "gradeBand": band, "summary": summ})
for domain, (band, summ) in YW_CLUSTER_SUM.items():
    new_clusters.append({"subject": "语文", "domain": domain,
                         "gradeBand": band, "summary": summ})
save('clusters.json', {"clusters": new_clusters})

print(f"道法节点 {len(df_nodes)}，道法边 {len(df_edges)}，边/点比 {len(df_edges)/len(df_nodes):.2f}")
print(f"语文节点 {len(yw_nodes)}，语文边 {len(yw_edges)}，边/点比 {len(yw_edges)/len(yw_nodes):.2f}")
print(f"总节点 {len(new_topics)}，总边 {len(new_deps)}，clusters {len(new_clusters)}")
