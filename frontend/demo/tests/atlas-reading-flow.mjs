import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildAtlas } from '../src/domain/atlas.js';

const f = JSON.parse(readFileSync(new URL('../prototypes/tree-of-wisdom/text/study-fixtures-analysis.json', import.meta.url)));
const sections = Object.entries(f.hierarchy).map(([id, s]) => ({ section_id: id, parent_section: s.parent, section_number: s.name.split(' · ')[0], section_name: s.name.split(' · ').at(-1), is_book_root: id === 'book' }));
const nodes = f.nodes.map(n => ({ knowledge_id: n.id, section_id: n.section, label: n.title }));
const deps = f.deps.map(([a,b]) => ({ source_knowledge_id: a, target_knowledge_id: b }));
const view = selected => buildAtlas(nodes, sections, deps, selected, { density: 'compact' });
const failures = [];
const check = (ok, message) => { if (!ok) failures.push(message); };
const one = view(1), fifteen = view(15);
const turn = one.edges.find(e => e.a === 25 && e.b === 27 && e.type === 'gap');
check(!!turn, '25→27 remains visible');
if (turn) {
  // The next reading row is below-left: do not circle behind the source card.
  check(turn.points.every(p => p.x <= turn.start.x && p.y >= turn.start.y),
    '25→27 follows the row transition without looping above/behind its source');
}
const approach = fifteen.edges.find(e => e.a === 13 && e.b === 32 && e.type === 'dependency');
check(!!approach, '13→32 remains visible');
if (approach) {
  const p = approach.points.at(-2), q = approach.points.at(-1);
  check(Math.hypot(q.x-p.x,q.y-p.y) >= 16, '13→32 has a full straight arrowhead stem');
}
const chapters = fifteen.parents.filter(g => g.depth === 0);
const first = chapters.find(g => g.id === 'foundations'), last = chapters.find(g => g.id === 'functions');
check(last.y > first.y && last.x === first.x, 'A later chapter starts below the first instead of stretching a tall row');
const twentyNine = view(29);
const across = twentyNine.edges.find(e => e.a === 27 && e.b === 34 && e.type === 'dependency');
const down = twentyNine.edges.find(e => e.a === 4 && e.b === 31 && e.type === 'dependency');
check(across?.points.length === 2, '27→34 keeps its unobstructed straight lane around item 29');
check(!!down, '4→31 remains visible around item 29');
if (across && down) for (let i=1;i<across.points.length;i++) for (let j=1;j<down.points.length;j++) {
  const a=across.points[i-1], b=across.points[i], c=down.points[j-1], d=down.points[j];
  if (a.y===b.y && c.y===d.y && Math.min(Math.max(a.x,b.x),Math.max(c.x,d.x))-Math.max(Math.min(a.x,b.x),Math.min(c.x,d.x))>24)
    check(Math.abs(a.y-c.y)>=8, 'Long horizontal approaches leave room beside a straight crossing route');
}
assert.deepEqual(failures, []);
console.log('Reading-row transition, arrowhead stem and balanced chapter placement passed.');
