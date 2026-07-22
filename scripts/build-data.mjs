// 根据 data/topics.json 与 data/dependencies.json 重新生成 data/manifest.json
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (n) => JSON.parse(readFileSync(join(root, 'data', n), 'utf8'));

const { topics } = read('topics.json');
const { dependencies } = read('dependencies.json');

const bySubject = {};
for (const t of topics) {
  bySubject[t.subject] ??= { total: 0, complete: 0, skeleton: 0, grades: new Set() };
  const s = bySubject[t.subject];
  s.total += 1;
  s[t.status] = (s[t.status] ?? 0) + 1;
  for (let g = t.gradeRangeStart; g <= t.gradeRangeEnd; g++) s.grades.add(g);
}
const subjectStats = Object.fromEntries(
  Object.entries(bySubject).map(([k, v]) => [k, {
    topics: v.total,
    complete: v.complete ?? 0,
    skeleton: v.skeleton ?? 0,
    gradeCoverage: [...v.grades].sort((a, b) => a - b),
  }])
);

const manifest = {
  name: '中国 K12 知识地图数据集',
  version: '0.1.0',
  generatedAt: new Date().toISOString().slice(0, 10),
  totals: {
    topics: topics.length,
    completeTopics: topics.filter(t => t.status === 'complete').length,
    skeletonTopics: topics.filter(t => t.status === 'skeleton').length,
    dependencies: dependencies.length,
    subjects: Object.keys(bySubject).length,
  },
  bySubject: subjectStats,
};
writeFileSync(join(root, 'data', 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`manifest 已更新：topics ${topics.length}（complete ${manifest.totals.completeTopics} / skeleton ${manifest.totals.skeletonTopics}），dependencies ${dependencies.length}`);
