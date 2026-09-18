import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildAtlas } from '../src/domain/atlas.js';

const sections = [];
for (let chapter = 0; chapter < 4; chapter++) {
  sections.push({ section_id: 10 + chapter, parent_section: null, section_number: String(chapter + 1), section_name: 'Chapter' });
  for (let part = 0; part < 2; part++) sections.push({ section_id: 30 + chapter * 2 + part, parent_section: 10 + chapter, section_number: `${chapter + 1}.${part + 1}`, section_name: 'Section' });
}
const nodes = Array.from({ length: 80 }, (_, i) => ({ knowledge_id: 101 + i, section_id: 30 + Math.floor(i / 10), label: `Object ${i + 1}` }));
const relation = (a, b) => ({ source_knowledge_id: 100 + a, target_knowledge_id: 100 + b });
const sparse = [relation(20, 28), relation(28, 39), relation(20, 19)];
const dense = Array.from({ length: 79 }, (_, i) => relation(i + 1, i + 2));
for (let i = 1; i < 70; i += 2) dense.push(relation(i, i + 9));
const edgeKeys = layout => layout.edges.map(edge => `${edge.type}:${edge.a}:${edge.b}`).sort();
const crosses = (a, b, rect) => a.x === b.x
  ? a.x > rect.l && a.x < rect.r && Math.max(a.y, b.y) > rect.t && Math.min(a.y, b.y) < rect.b
  : a.y > rect.t && a.y < rect.b && Math.max(a.x, b.x) > rect.l && Math.min(a.x, b.x) < rect.r;
const samples = [];
for (const view of ['reading', 'hierarchy']) for (const limit of [8, 16, 24]) for (const relationships of [sparse, dense]) {
  const options = { view, limit, book: relationships === sparse ? 1 : 24, dependency: 2 };
  const selected = relationships === sparse ? 120 : 140;
  const regular = buildAtlas(nodes, sections, relationships, selected, options);
  const compact = buildAtlas(nodes, sections, relationships, selected, { ...options, density: 'compact' });
  assert.deepEqual(compact.placed.map(node => node.knowledge_id), regular.placed.map(node => node.knowledge_id));
  assert.deepEqual(edgeKeys(compact), edgeKeys(regular), `${view}/${limit}: all relationships remain routed`);
  assert.equal(compact.omitted, regular.omitted, 'compression does not add omitted arrows');
  assert.equal(compact.unlabelled, 0, `${view}/${limit}/${relationships === sparse ? 'sparse' : 'dense'}: every gap keeps its label`);
  assert(compact.width < regular.width && compact.height < regular.height, `${view}/${limit}: both drawing dimensions shrink`);
  assert.equal(compact.nodeHeight, 52, "compact cards reclaim the number row");
  const obstacles = [...compact.obstacles, ...compact.placed.map(node => ({ l: node.x, r: node.x + compact.nodeWidth, t: node.y, b: node.y + compact.nodeHeight }))];
  for (const edge of compact.edges) for (let i = 1; i < edge.points.length; i++) {
    const a = edge.points[i - 1], b = edge.points[i];
    assert(a.x === b.x || a.y === b.y, `${view}/${limit}: arrows remain orthogonal ${JSON.stringify({a,b})}`);
    assert(!obstacles.some(rect => crosses(a, b, rect)), `${view}/${limit}: arrow ${edge.a}→${edge.b} crosses a card or heading`);
  }
  for (let i = 0; i < compact.placed.length; i++) for (const b of compact.placed.slice(i + 1)) {
    const a = compact.placed[i];
    assert(!(a.x < b.x + compact.nodeWidth && a.x + compact.nodeWidth > b.x && a.y < b.y + compact.nodeHeight && a.y + compact.nodeHeight > b.y), 'cards do not overlap');
  }
  samples.push({ view, limit, relationships: relationships === sparse ? 'sparse' : 'dense', widthReduction: `${Math.round((1 - compact.width / regular.width) * 100)}%`, heightReduction: `${Math.round((1 - compact.height / regular.height) * 100)}%` });
}
const analysis = JSON.parse(readFileSync(new URL('../prototypes/tree-of-wisdom/text/study-fixtures-analysis.json', import.meta.url), 'utf8'));
const analysisSections = Object.entries(analysis.hierarchy).map(([id, section]) => ({ section_id: id, parent_section: section.parent, section_number: section.name.split(' · ')[0], section_name: section.name.split(' · ').at(-1), is_book_root: id === 'book' }));
const analysisNodes = analysis.nodes.map(node => ({ knowledge_id: node.id, section_id: node.section, label: node.title }));
const analysisEdges = analysis.deps.map(([a, b]) => ({ source_knowledge_id: a, target_knowledge_id: b }));
for (const view of ['reading', 'hierarchy']) for (const selected of [1, 2, 4, 13, 25, 29, 36]) {
  const regular = buildAtlas(analysisNodes, analysisSections, analysisEdges, selected, { view });
  const compact = buildAtlas(analysisNodes, analysisSections, analysisEdges, selected, { view, density: 'compact' });
  assert.deepEqual(edgeKeys(compact), edgeKeys(regular), `Real Analysis ${selected}/${view}: relationships stay visible`);
  assert.equal(compact.unlabelled, 0, `Real Analysis ${selected}/${view}: all omitted ranges have labels`);
}
console.log(JSON.stringify({ compactAtlas: 'passed', realAnalysisCases: 14, samples }, null, 2));
