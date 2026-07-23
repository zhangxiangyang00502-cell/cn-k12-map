"""题目详情解析：data.json -> quiz 格式；过滤非单选/含图表/答案异常。"""
import re
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from smartedu_lib import strip_html

LETTERS = "ABCDEFGH"


def parse_question(data):
    """返回 dict(q, options, answer, explain) 或 (None, reason)。"""
    content = data.get("content") or {}
    title_html = content.get("title") or ""
    q = strip_html(title_html)
    if not q:
        return None, "empty_stem"
    if "<img" in title_html or "<table" in title_html:
        return None, "stem_has_img_table"

    # 选项：content.items[].choices[]
    options, opt_htmls = [], []
    for item in content.get("items") or []:
        for ch in item.get("choices") or []:
            ident = (ch.get("identifier") or "").strip().upper()
            txt_html = ch.get("text") or ""
            if "<img" in txt_html or "<table" in txt_html:
                return None, "option_has_img_table"
            options.append((ident, strip_html(txt_html)))
            opt_htmls.append(txt_html)
    # 去重保持顺序
    seen, opts = set(), []
    for ident, txt in options:
        if ident and ident not in seen:
            seen.add(ident)
            opts.append((ident, txt))
    if len(opts) < 2:
        return None, "too_few_options"
    if any(not t for _, t in opts):
        return None, "empty_option"

    # 答案
    corrects = []
    for resp in content.get("responses") or []:
        for c in resp.get("corrects") or []:
            corrects.append(str(c).strip().upper())
    corrects = [c for c in corrects if c]
    if len(corrects) != 1:
        return None, "not_single_answer"
    ans = corrects[0]
    valid = {ident for ident, _ in opts}
    if ans not in valid or ans not in LETTERS[:4] or len(valid) > 4:
        # 选项超过4或答案不在A-D内：仍允许答案在选项内且<=4个选项
        if ans not in valid or len(valid) > 4:
            return None, "answer_out_of_range"

    # 排序按 identifier
    opts.sort(key=lambda x: LETTERS.index(x[0]) if x[0] in LETTERS else 99)
    options_out = [f"{ident}. {txt}" for ident, txt in opts]

    # 解析
    explain = ""
    fbs = content.get("feedbacks") or []
    if fbs:
        explain = strip_html((fbs[0] or {}).get("content") or "")

    return {"q": q, "options": options_out, "answer": ans, "explain": explain}, None


def entry_is_single_choice(entry):
    tags = [t.get("tag_name", "") for t in entry.get("tag_list") or []]
    joined = "|".join(tags)
    if any(k in joined for k in ("多选", "不定项", "判断", "填空", "解答", "简答", "主观", "材料分析", "辨析", "论述")):
        return False
    return "单选" in joined or "选择" not in joined  # 未标注题型的也尝试，由详情再判
