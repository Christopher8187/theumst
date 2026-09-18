import assert from 'node:assert/strict';
import { notebookMathRows } from '../src/domain/notebook-math.js';

const inline = notebookMathRows('Let $x$ be real and \\(y=2\\) remain inline.');
assert.equal(inline.length, 1);
assert.equal(inline[0].type, 'text');
assert(!inline[0].html.includes('katex-display'));
const mixed = notebookMathRows('Before $x$.\n\n$$\\sum_{i=1}^{n} i$$\nAfter.\\[\\begin{matrix}a&b\\\\c&d\\end{matrix}\\]End.');
assert.deepEqual(mixed.map(row => row.type), ['text','display','text','display','text']);
assert(mixed.filter(row=>row.type==='display').every(row=>row.html.includes('katex-display')));
assert(mixed.filter(row=>row.type==='text').every(row=>!row.html.startsWith('<br>')&&!row.html.endsWith('<br>')));
assert.equal(notebookMathRows('')[0], undefined);
assert(notebookMathRows('<script>alert(1)</script>')[0].html.startsWith('&lt;script&gt;'));
console.log('Notebook inline/display separation, surrounding line breaks and escaping passed.');
