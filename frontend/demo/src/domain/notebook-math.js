import { renderMath } from '../math.js';

// Display delimiters make a new writing row; inline delimiters stay in prose.
export function notebookMathRows(value) {
  const source = String(value || '');
  const rows = [];
  let cursor = 0;
  const display = /(?<!\\)\$\$[\s\S]+?(?<!\\)\$\$|\\\[[\s\S]+?\\\]/g;
  const textRow = text => {
    const trimmed = text.replace(/^\s*\n|\n\s*$/g, '');
    if (trimmed.trim()) rows.push({ type: 'text', html: renderMath(trimmed) });
  };
  for (const match of source.matchAll(display)) {
    textRow(source.slice(cursor, match.index));
    rows.push({ type: 'display', html: renderMath(match[0]) });
    cursor = match.index + match[0].length;
  }
  textRow(source.slice(cursor));
  return rows;
}
