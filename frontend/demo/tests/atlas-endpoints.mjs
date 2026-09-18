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
assert.deepEqual(failures, []);
console.log('Adaptive chapter rows, distinct tips/tails, arrowhead clearance and +5 placement passed.');
