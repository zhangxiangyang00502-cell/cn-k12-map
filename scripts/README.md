# 国家中小学智慧教育平台 资源管线说明（R5 课程包五件套）

> 维护范围：`scripts/build_resources_pack.py` → `data/resources_pack.json`
> 上游依赖：`data/resources.json` 中 `type=course` 且带 `activityId` 的课时深链。

## 接口清单

### 免登录（可直接 GET，HTTP 200）

| 用途 | 接口 |
|---|---|
| 教材目录 | `https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/teachingmaterials/part_{100,101,102}.json` |
| 课程章节树 | `https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/trees/{tmId}.json` |
| 课程资源索引 | `https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/national_lesson/teachingmaterials/{tmId}/resources/parts.json` |
| **课程包详情（五件套元数据）** | `https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/national_lesson/resources/details/{activityId}.json` |
| 精品课包详情（回退） | `https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/{activityId}.json` |
| 缩略图/预览图 | `https://r{1,2,3}-ndr.ykt.cbern.com.cn/edu_product/...` （公开 CDN） |
| 课时播放页 | `https://basic.smartedu.cn/syncClassroom/classActivity?activityId=..&chapterId=..&teachingmaterialId=..&fromPrepare=0&classHourId=lesson_1` （无 X-Frame-Options，可 iframe 内嵌，五件套在页内可看） |

说明：
- 常规课程包（`national_lesson`）五件套在详情的 `relations.national_course_resource[]`；
  精品课包（`elite_lesson`，仅三件套：微课视频/学习任务单/作业练习）走回退接口，
  关联资源在 `relations.course_resource[]`。national_lesson 详情接口对 elite_lesson
  的 activityId 返回 **403**，不是网络错误，按类型换接口即可。
- 每件资源的 `custom_properties.alias_name` 即中文类型名：
  `视频课程`/`微课视频`、`课件`、`教学设计`、`学习任务单`、`课后练习`/`作业练习`。
  格式、大小、时长在 `custom_properties.format/size/duration`。

### 需要登录态（不要硬爬）

| 用途 | 接口/域 | 现状 |
|---|---|---|
| 文件本体下载（mp4/m3u8/pdf/docx/pptx） | `https://r{1,2,3}-ndr-private.ykt.cbern.com.cn/edu_product/...` | 无凭证 **401 Authorization Required**（openresty 校验） |
| 电子教材包下载 | `https://r{1,2}-ndr-doc-private.ykt.cbern.com.cn/...` | 同上 401 |

- 直链地址可从详情 json 的 `ti_items[].ti_storages[]` 拿到（本管线已落盘到
  `resources_pack.json` 各件的 `downloadUrl`，并标 `requiresAuth: true`）。
- 需要什么凭证：响应头 `access-control-allow-headers` 显示服务端接受
  `Authorization` 和 `x-nd-auth`。即在 basic.smartedu.cn 登录后的会话凭证
  （Cookie + 页面签发的 `x-nd-auth` 令牌）。没有官方开放 API 文档，属逆向范畴，
  按 PRD 合规要求不硬爬；产品侧一律引导用户在播放页（playUrl）内查看/下载。
- 第三方下载器（如 FlyEduDownloader，缓存里有其源码
  `data/raw_smartedu/FlyEduDownloader_MainForm.vb`）也是带登录态会话访问这些地址。

## 数据产出

`data/resources_pack.json`：

```
{
  "meta": { "source", "detailApi", "detailApiFallback", "note",
            "stats": {...}, "incomplete_detail": [...] },
  "packs": [
    { "topicId": "...",            // 与 resources.json 相同的关联键
      "items": [
        { "activityId", "chapterId", "teachingmaterialId",
          "packageType": "national_lesson | elite_lesson",
          "lessonTitle", "playUrl", "source",
          "pack": {
            "video":      [ {resourceId,title,typeName,resourceType,lessonTag,
                             format,sizeBytes,duration,thumb,downloadUrl,requiresAuth} ],
            "courseware": [...],   // 课件
            "lessonPlan": [...],   // 教学设计
            "taskSheet":  [...],   // 学习任务单
            "exercise":   [...]    // 课后练习
          } } ] } ]
}
```

- `thumb`：免登录公开 CDN 图（抽样 curl 全部 200）。
- `downloadUrl`：文件直链，`requiresAuth: true` 表示需平台登录态（当前全部为 true）。
- 缺件情况见 `meta.incomplete_detail`：精品课包天然没有课件/教学设计；
  个别专题视频（如"文学文化常识和名著阅读"）平台未挂附件。

## 复跑

```bash
python3 scripts/build_resources_pack.py
```

详情 json 缓存在 `data/raw_smartedu/detail_{activityId}.json` /
`detail_fallback_{activityId}.json`，删缓存可强制刷新。限流 0.2s/次 + 3 次重试。
