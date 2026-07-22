// 数据校验：引用完整性 + DAG（无环）+ 基本字段检查
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const data = (n) => JSON.parse(readFileSync(join(root, 'data', n), 'utf8'));

const { topics } = data('topics.json');
const { dependencies } = data('dependencies.json');
const { curricula } = data('curriculum-standards.json');

let errors = 0;
const fail = (msg) => { errors += 1; console.error('  ✗ ' + msg); };

// 1. topic id 唯一性
const ids = new Set();
for (const t of topics) {
  if (ids.has(t.id)) fail(`重复的 topic id: ${t.id}`);
  ids.add(t.id);
}
console.log(`[1] 共 ${topics.length} 个知识点，id 唯一性检查完成`);

// 2. 基本字段
const TYPES = new Set(['CONCEPTUAL', 'PROCEDURAL', 'REPRESENTATIONAL', 'LANGUAGE', 'META']);
const STATUS = new Set(['complete', 'skeleton']);
for (const t of topics) {
  if (!TYPES.has(t.type)) fail(`${t.id}: 非法 type "${t.type}"`);
  if (!STATUS.has(t.status)) fail(`${t.id}: 非法 status "${t.status}"`);
  if (!t.name || !t.description) fail(`${t.id}: 缺少 name/description`);
  if (!(t.gradeRangeStart >= 1 && t.gradeRangeEnd <= 12 && t.gradeRangeStart <= t.gradeRangeEnd))
    fail(`${t.id}: 年级范围非法 ${t.gradeRangeStart}-${t.gradeRangeEnd}`);
}
console.log('[2] 字段类型与年级范围检查完成');

// 3. standards 引用存在
const stdKeys = new Set(curricula.flatMap(c => c.standards.map(s => s.key)));
for (const t of topics) {
  for (const k of t.standards ?? []) {
    if (!stdKeys.has(k)) fail(`${t.id}: 引用了不存在的课标 key "${k}"`);
  }
}
console.log(`[3] 课标引用检查完成（已注册 ${stdKeys.size} 条课标 key）`);

// 4. dependency 引用完整性 + strength 合法
for (const d of dependencies) {
  if (!ids.has(d.topicId)) fail(`悬空引用 topicId: ${d.topicId}`);
  if (!ids.has(d.prerequisiteId)) fail(`悬空引用 prerequisiteId: ${d.prerequisiteId}`);
  if (d.topicId === d.prerequisiteId) fail(`自环: ${d.topicId}`);
  if (!['hard', 'soft'].includes(d.strength)) fail(`非法 strength: ${d.topicId} -> ${d.prerequisiteId}`);
  if (!d.reason || d.reason.length < 6) fail(`reason 过于敷衍: ${d.topicId} -> ${d.prerequisiteId}`);
}
console.log(`[4] 共 ${dependencies.length} 条先修边，引用完整性检查完成`);

// 5. 无环检查（Kahn 拓扑排序，方向：prerequisite → topic）
const indeg = new Map([...ids].map(id => [id, 0]));
const adj = new Map([...ids].map(id => [id, []]));
for (const d of dependencies) {
  if (ids.has(d.topicId) && ids.has(d.prerequisiteId)) {
    adj.get(d.prerequisiteId).push(d.topicId);
    indeg.set(d.topicId, indeg.get(d.topicId) + 1);
  }
}
const queue = [...ids].filter(id => indeg.get(id) === 0);
let visited = 0;
while (queue.length) {
  const cur = queue.shift();
  visited += 1;
  for (const next of adj.get(cur)) {
    indeg.set(next, indeg.get(next) - 1);
    if (indeg.get(next) === 0) queue.push(next);
  }
}
if (visited !== ids.size) {
  const inCycle = [...ids].filter(id => indeg.get(id) > 0);
  fail(`检测到环！涉及 ${inCycle.length} 个节点: ${inCycle.slice(0, 10).join(', ')}${inCycle.length > 10 ? ' …' : ''}`);
  console.log('[5] DAG 检查失败');
} else {
  console.log('[5] DAG 检查通过：无环（拓扑排序访问了全部节点）');
}

// 6. 统计输出
const bySubject = {};
for (const t of topics) {
  bySubject[t.subject] ??= { total: 0, complete: 0, skeleton: 0 };
  bySubject[t.subject].total += 1;
  bySubject[t.subject][t.status] += 1;
}
console.log('\n各学科统计:');
for (const [s, v] of Object.entries(bySubject)) {
  console.log(`  ${s}: ${v.total} 个知识点 (complete ${v.complete} / skeleton ${v.skeleton})`);
}
const dfEdges = dependencies.filter(d => d.topicId.startsWith('cn_df_')).length;
const dfTopics = topics.filter(t => t.subject === '道德与法治').length;
console.log(`\n道法学科: ${dfTopics} 个知识点, ${dfEdges} 条内部先修边 (边/点比 ${(dfEdges / dfTopics).toFixed(2)})`);

if (errors > 0) {
  console.error(`\n校验失败：共 ${errors} 个错误`);
  process.exit(1);
} else {
  console.log('\n✓ 全部校验通过');
}
