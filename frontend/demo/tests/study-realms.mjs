import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { adjacentStudyNode, realmForNode } from '../prototypes/tree-of-wisdom/text/studyNavigation.ts';
import { buildAtlas } from '../src/domain/atlas.js';

const nodes = [
  { knowledge_id: 101, type: 'definition' },
  { knowledge_id: 207, type: 'exercise' },
  { knowledge_id: 305, type: 'exercise', completed: true },
  { knowledge_id: 411, type: 'theorem' },
  { knowledge_id: 509, type: 'exercise' },
].map((node, position) => ({ ...node, section_id: 'one', label: `Object ${position+1}` }));
assert.equal(adjacentStudyNode(nodes, 101, 'text', 1)?.knowledge_id, 411);
assert.equal(adjacentStudyNode(nodes, 411, 'text', 1), undefined);
assert.equal(adjacentStudyNode(nodes, 207, 'questions', 1)?.knowledge_id, 305, 'Questions includes completed exercises');
assert.equal(adjacentStudyNode(nodes, 509, 'questions', -1)?.knowledge_id, 305);
assert.equal(adjacentStudyNode(nodes, 207, 'questions', -1), undefined, 'Previous exercise never wraps');
assert.equal(adjacentStudyNode(nodes, 509, 'questions', 1), undefined, 'Next exercise never wraps');
assert.equal(adjacentStudyNode(nodes, 999, 'text', 1), undefined);
assert.equal(realmForNode(nodes[0]), 'text');
assert.equal(realmForNode(nodes[1]), 'questions');

const sections = [{ section_id: 'one', parent_section: null, section_name: 'One' }];
const relations = [{ source_knowledge_id:101, target_knowledge_id:411 }];
const text = buildAtlas(nodes, sections, relations, 101, { density:'compact', book:24, excludedTypes:['exercise'] });
assert.deepEqual(text.placed.map(node => [node.knowledge_id,node.id]), [[101,1],[411,4]], 'Text keeps original reader numbers');
assert(text.edges.some(edge => edge.type==='gap' && edge.a===1 && edge.b===4 && edge.count===2), 'Gold count includes the omitted exercises');
assert(text.edges.some(edge => edge.type==='dependency' && edge.a===1 && edge.b===4));
const questions = buildAtlas(nodes, sections, relations, 207, { density:'compact', book:24 });
assert.equal(questions.placed.length, nodes.length, 'Questions permits every working type');
const empty = buildAtlas(nodes.filter(node=>node.type==='exercise'), sections, [], 207, { excludedTypes:['exercise'] });
assert.deepEqual(empty.placed, []);
assert(Number.isFinite(empty.width) && Number.isFinite(empty.height));

// Use the frozen grimoire as well as deliberately nonsequential IDs.
const f=JSON.parse(readFileSync(new URL('../prototypes/tree-of-wisdom/text/study-fixtures-analysis.json',import.meta.url)));
const bookNodes=f.nodes.map(n=>({knowledge_id:n.id,section_id:n.section,label:n.title,type:n.type}));
const bookSections=Object.entries(f.hierarchy).map(([id,s])=>({section_id:id,parent_section:s.parent,section_name:s.name,is_book_root:id==='book'}));
const bookDeps=f.deps.map(([a,b])=>({source_knowledge_id:a,target_knowledge_id:b}));
for (const view of ['reading','hierarchy']) for (const selected of bookNodes.filter(node=>node.type!=='exercise').map(node=>node.knowledge_id)) {
  const layout=buildAtlas(bookNodes,bookSections,bookDeps,selected,{view,density:'compact',excludedTypes:['exercise']});
  assert(layout.placed.every(node=>node.type!=='exercise'));
  assert(layout.placed.every(node=>node.id===node.knowledge_id));
  assert.equal(layout.omitted,0,`${view}/${selected}: relationships remain routed`);
  assert.equal(layout.unlabelled,0,`${view}/${selected}: omitted ranges retain counts`);
}
console.log('Realm navigation, type filtering, stable numbering and omitted counts passed.');
