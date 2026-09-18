import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildAtlas } from '../src/domain/atlas.js';

const f = JSON.parse(readFileSync(new URL('../prototypes/tree-of-wisdom/text/study-fixtures-analysis.json', import.meta.url)));
const sections = Object.entries(f.hierarchy).map(([id, s]) => ({ section_id: id, parent_section: s.parent, section_number: s.name.split(' · ')[0], section_name: s.name.split(' · ').at(-1), is_book_root: id === 'book' }));
const nodes = f.nodes.map(n => ({ knowledge_id: n.id, section_id: n.section, label: n.title }));
const deps = f.deps.map(([a, b]) => ({ source_knowledge_id: a, target_knowledge_id: b }));
const layout = buildAtlas(nodes, sections, deps, 1, { density: 'compact' });
const edge = (a, b) => { const e = layout.edges.find(e => e.a === a && e.b === b); assert(e, `${a}→${b} remains visible`); return e; };
const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };
for (const [a,b] of [[1,27],[2,27],[4,25]]) {
  const route = edge(a,b).points;
  check(route[2].y === route[1].y && route[2].x-route[1].x > 40,
    `${a}→${b} should depart right without a short down-and-up wedge`);
}
const chapters = layout.parents.filter(g => g.depth === 0);
check(chapters[0].y === chapters[2].y, 'Differentiation must fit beside Foundations and Integration');
check(chapters[3].y > chapters[0].y, 'The wide fourth chapter belongs on the next row');
for (const [incoming, outgoing] of [[edge(19,25),edge(25,27)],[edge(25,27),edge(27,34)]]) {
  check(Math.hypot(incoming.end.x-outgoing.start.x,incoming.end.y-outgoing.start.y)>=12, `${incoming.a}→${incoming.b} tip must not meet ${outgoing.a}→${outgoing.b} tail`);
}
const terminal = edge(4,31), p = terminal.points.at(-2), q = terminal.points.at(-1);
check(Math.hypot(q.x-p.x,q.y-p.y)>=16, '4→31 must enter through the base of a full arrowhead');
check(edge(4,25).end.y > edge(19,25).end.y, '4→25 uses a lower port than the golden 19→25 arrow');
const badge = layout.badges.find(b => b.a===19 && b.b===25);
check(badge && badge.y+badge.h < badge.anchorY, '+5 sits above its golden 19→25 arrow');
const around13 = buildAtlas(nodes, sections, deps, 13, { density: 'compact' });
const dependency13 = (a,b) => around13.edges.find(e=>e.a===a&&e.b===b&&e.type==='dependency');
for (const [a,b] of [[4,31],[8,15],[13,15]]) {
  const e = dependency13(a,b);
  check(!!e, `${a}→${b} remains visible around item 13`);
  if (!e) continue;
  const last = e.points.at(-1), approach = e.points.at(-2);
  const dx = Math.sign(last.x-approach.x), dy = Math.sign(last.y-approach.y);
  for (let i=1;i<e.points.length-1;i++) {
    const p=e.points[i-1],q=e.points[i];
    check((q.x-p.x)*dx+(q.y-p.y)*dy>=0,
      `${a}→${b} approaches monotonically instead of moving its hook earlier`);
  }
}
const tail31=dependency13(29,31).start,tail32=dependency13(29,32).start;
check(Math.hypot(tail31.x-tail32.x,tail31.y-tail32.y)>=8,
  '29→31 and 29→32 have separate departure points');
// Geometry must depend on relationships and reader order, not these IDs/names.
const renameId = id => id * 101 + 7000;
const renamed = buildAtlas(
  nodes.map(n => ({ ...n, knowledge_id: renameId(n.knowledge_id), label: `Renamed ${n.knowledge_id}` })),
  sections.map(s => ({ ...s, section_name: `Renamed ${s.section_id}` })),
  deps.map(e => ({ source_knowledge_id: renameId(e.source_knowledge_id), target_knowledge_id: renameId(e.target_knowledge_id) })),
  renameId(13), { density: 'compact' },
);
const geometry = l => ({
  nodes: l.placed.map(n => [n.id, n.x, n.y]),
  edges: l.edges.map(e => [e.type, e.a, e.b, e.points]),
  omitted: l.omitted,
});
assert.deepEqual(geometry(renamed), geometry(around13), 'renaming IDs and labels leaves routing unchanged');
assert.deepEqual(failures, []);
console.log('Adaptive chapter rows, distinct tips/tails, hook-free approaches and renamed-ID geometry passed.');
