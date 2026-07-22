# 中国 K12 知识地图（cn-k12-map）

一个「中国 K12 知识点树 + 交互式知识地图」项目：把中国 K12 阶段（小学 1 年级到高中 12 年级）的知识点组织成一张**有向无环的先修依赖图**，并用一个单页交互地图可视化。

- **每个点** = 一个微知识点（topic）
- **颜色** = 学科（15 个学科）
- **纵轴** = 年级（1 在下，12 在上）
- **连线** = 先修关系（hard = 真正的逻辑前置，soft = 学了更好）

数据 schema 与可视化思路借鉴开源项目 Marble Skill Taxonomy 的设计思想（不复制其任何内容），全部内容为中文原创撰写。

## 数据现状

| 学科 | 知识点数 | 状态 |
|---|---|---|
| 道德与法治（初中六册 24 单元） | 130 | ✅ 完整填充（含描述、掌握证据、家长检验话术、课标对齐） |
| 语文 / 数学 / 英语 / 科学 / 物理 / 化学 / 生物 / 历史 / 地理 / 思想政治 / 信息科技 / 体育与健康 / 艺术 / 劳动 | 149 | 🟡 骨架占位（有名称、简介、年级和纵向进阶边，内容待填充） |

先修依赖边共 270 条，其中道法内部 174 条（边/点比 1.34），跨单元、跨年级连边。课标对齐引用《义务教育课程方案和课程标准（2022 年版）》道德与法治学科五大主题（生命安全与健康教育 / 法治教育 / 中华优秀传统文化教育 / 革命传统教育 / 国情教育）× 第四学段（7–9 年级）。

## 快速开始

```bash
npm install
npm run dev        # vite 静态服务器，浏览器打开提示的地址
```

交互说明：

- **滚轮**缩放，**拖拽**平移
- **点击节点**：右侧显示详情（描述、类型、年级、掌握证据、家长检验话术、课标对齐、单元概述），并高亮它的「先修链」（向上递归：先学这些）和「解锁链」（向下递归：学会后能解锁什么）
- **hover**：显示名称 tooltip
- **搜索框**：按名称 / 描述 / 单元模糊搜索，点击结果直达
- **学科 chips**：按学科显示 / 隐藏
- 默认只显示道法学科内部的先修边，勾选「显示全部先修线」可看到骨架学科的纵向进阶边

## 数据校验

```bash
npm run validate     # 校验：id 唯一、无悬空引用、无环（拓扑排序）、字段合法
npm run build-data   # 编辑 data/topics.json / dependencies.json 后，重新生成 manifest.json
```

## 目录结构

```
cn-k12-map/
  package.json
  index.html                     # 交互式知识地图（纯前端 Canvas 单页）
  data/
    topics.json                  # 微知识点（图节点）
    dependencies.json            # 先修依赖边（DAG）
    curriculum-standards.json    # 课标条目
    clusters.json                # 每个学科×领域的家长友好概述
    manifest.json                # 数量统计（由 build-data 生成）
  scripts/
    build-data.mjs               # 重新生成 manifest.json
    validate.mjs                 # 校验脚本
```

## 数据 schema

### topics.json

```json
{
  "topics": [{
    "id": "cn_df_xf_01",
    "type": "CONCEPTUAL | PROCEDURAL | REPRESENTATIONAL | LANGUAGE | META",
    "subject": "道德与法治",
    "domain": "坚持宪法至上",
    "name": "宪法是国家的根本法",
    "description": "1-2 句白话解释",
    "gradeRangeStart": 8,
    "gradeRangeEnd": 8,
    "status": "complete | skeleton",
    "evidence": ["能说出……", "能举例……"],
    "assessmentPrompt": "如果孩子……，能……吗？",
    "standards": ["yw-2022:道德与法治.法治教育.第四学段"]
  }]
}
```

### dependencies.json

```json
{
  "dependencies": [{
    "topicId": "cn_df_xf_01",
    "prerequisiteId": "cn_df_fz_02",
    "strength": "hard | soft",
    "reason": "一句话说明为什么先学它（必须具体）"
  }]
}
```

必须是**有向无环图（DAG）**，`validate.mjs` 会做拓扑排序检查。

## 内容原则

- 道法内容按人教版《道德与法治》六册 24 个单元组织，贴合教材与中考考纲，不编造概念
- description 说人话（家长能看懂），evidence 是可观察的掌握标准
- 依赖边的 reason 必须写具体逻辑（为什么它是前置），禁止「因为需要先学」式废话
- 骨架学科节点只搭结构，界面中明确标注「骨架占位，内容待填充」
