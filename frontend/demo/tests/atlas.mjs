import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { buildAtlas } from '../src/domain/atlas.js';
import { renderMath } from '../src/math.js';

const sections=[{section_id:1,parent_section:null,section_number:'0',section_name:'Whole book'}];
for(let i=0;i<4;i++){
  sections.push({section_id:10+i,parent_section:1,section_number:String(i+1),section_name:`Part ${i+1}`});
  sections.push({section_id:20+i,parent_section:10+i,section_number:`${i+1}.1`,section_name:'Chapter'});
  for(let j=0;j<2;j++)sections.push({section_id:30+i*2+j,parent_section:20+i,section_number:`${i+1}.1.${j+1}`,section_name:'Section'});
}
const nodes=Array.from({length:80},(_,i)=>({knowledge_id:101+i,section_id:30+Math.floor(i/10),label:`Item ${i+1}: $x^2$`,completed:i%3===0}));
const relation=(a,b)=>({source_knowledge_id:nodes[a-1].knowledge_id,target_knowledge_id:nodes[b-1].knowledge_id,relation_type:'uses'});
const sparse=[relation(20,28),relation(28,39),relation(20,19)];
for(const view of ['reading','hierarchy']){
 const result=buildAtlas(nodes,sections,sparse,120,{book:1,dependency:1,view});
 assert.deepEqual(result.placed.map(n=>n.id),[19,20,21,28]);
 assert.equal(result.badges[0].count,6);
 assert.equal(result.badges[0].a,21);
 assert.equal(result.badges[0].b,28);
 assert.ok(result.edges.some(e=>e.type==='order'&&e.a===19&&e.b===20));
 assert.ok(result.edges.some(e=>e.type==='dependency'&&e.a===20&&e.b===19));
 assert.ok(!result.parents.some(p=>p.id==='1'),'whole-book root does not become a direct-subsection border');
 assert.ok(result.parents.some(p=>p.depth>0),'intermediate nested sections retain grouping');
 assert.equal(result.omitted,0);
 assert.equal(result.unlabelled,0);
 assert.ok(result.placed.every(n=>n.completed===nodes[n.id-1].completed),'visiting does not change completion');
}
assert.equal(buildAtlas([],[],[],null).placed.length,0);
assert.deepEqual(buildAtlas(nodes,sections,[],120,{book:0,dependency:0}).placed.map(n=>n.id),[20]);
assert.match(renderMath('Inline $x^2$ and display $$x\\geq0$$'),/class="katex"/);
assert.match(renderMath('Inline $x^2$ and display $$x\\geq0$$'),/class="katex-display"/);
assert.doesNotMatch(renderMath('<img src=x onerror=alert(1)>'),/<img/);

const samples=[];
for(const limit of [8,16,24])for(const view of ['reading','hierarchy']){
 const edges=Array.from({length:79},(_,i)=>relation(i+1,i+2));
 for(let i=1;i<70;i+=2)edges.push(relation(i,i+9));
 const times=[];let layout;
 for(let repeat=0;repeat<3;repeat++){
  const start=performance.now();layout=buildAtlas(nodes,sections,edges,140,{book:24,dependency:2,limit,view});times.push(performance.now()-start);
 }
 assert.ok(layout.placed.length<=limit);
 assert.ok(layout.edges.every(e=>e.points.length>=2));
 samples.push({limit,view,objects:layout.placed.length,arrows:layout.edges.length,omitted:layout.omitted,unlabelled:layout.unlabelled,median_ms:+times.sort((a,b)=>a-b)[1].toFixed(1),max_ms:+Math.max(...times).toFixed(1)});
}
console.log(JSON.stringify({atlas:'passed',synthetic:true,samples},null,2));
