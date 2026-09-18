import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildAtlas } from '../src/domain/atlas.js';

// The reader's reported Real Analysis view, including the intervening chapters.
const fixture = JSON.parse(readFileSync(new URL('../prototypes/tree-of-wisdom/text/study-fixtures-analysis.json', import.meta.url), 'utf8'));
const sections = Object.entries(fixture.hierarchy).map(([id, s]) => ({ section_id: id, parent_section: s.parent, section_number: s.name.split(' · ')[0], section_name: s.name.split(' · ').at(-1), is_book_root: id === 'book' }));
const nodes = fixture.nodes.map(n => ({ knowledge_id: n.id, section_id: n.section, label: n.title }));
const dependencies = fixture.deps.map(([a, b]) => ({ source_knowledge_id: a, target_knowledge_id: b }));
const layout = buildAtlas(nodes, sections, dependencies, 1, { density: 'compact' });
const edge = (a, b, type = 'dependency') => {
  const result = layout.edges.find(e => e.a === a && e.b === b && e.type === type);
  assert(result, `${type} ${a}→${b} remains visible`);
  return result;
};
const segments = points => points.slice(1).map((b, i) => ({ a: points[i], b }));
function crowded(a, b) {
  const vertical = a.a.x === a.b.x;
  if (vertical !== (b.a.x === b.b.x)) return false;
  const along = vertical ? 'y' : 'x', across = vertical ? 'x' : 'y';
  const overlap = Math.min(Math.max(a.a[along], a.b[along]), Math.max(b.a[along], b.b[along]))
    - Math.max(Math.min(a.a[along], a.b[along]), Math.min(b.a[along], b.b[along]));
  return overlap > 16 && Math.abs(a.a[across] - b.a[across]) < 8;
}
const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };
for (const e of [edge(1, 2, 'order'), edge(2, 3, 'order'), edge(2, 3), edge(1, 4)]) {
  check(e.points.length === 2, `${e.type} ${e.a}→${e.b} should run straight between aligned cards`);
}
for (const [a, b] of [[edge(1, 27), edge(2, 27)], [edge(1, 27), edge(1, 2, 'order')], [edge(2, 27), edge(2, 3, 'order')], [edge(2, 27), edge(2, 3)]]) {
  check(!segments(a.points).some(s => segments(b.points).some(t => crowded(s, t))), `${a.a}→${a.b} and ${b.a}→${b.b} need distinct lanes`);
}
for (const group of layout.parents.filter(g => ['foundations', 'functions'].includes(g.id))) {
  const border = [{ x: group.x, y: group.y }, { x: group.x + group.w, y: group.y }, { x: group.x + group.w, y: group.y + group.h }, { x: group.x, y: group.y + group.h }, { x: group.x, y: group.y }];
  check(!segments(edge(1, 27).points).some(s => segments(border).some(t => crowded(s, t))), `1→27 must not trace the ${group.id} border`);
}
const pointwise = layout.tiles.find(g => g.id === 'pointwise');
const uniform = layout.parents.find(g => g.id === 'uniform');
check(uniform.x - pointwise.x - pointwise.w <= 64, '4.1 and 4.2 should be separated by one compact gutter');
assert.deepEqual(failures, []);
console.log('Real Analysis: straight arrows, distinct lanes, border clearance and compact 4.1–4.2 spacing passed.');
