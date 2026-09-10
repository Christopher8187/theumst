import katex from "katex";

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function renderMath(value) {
  const source = String(value || "");
  let cursor = 0;
  let output = "";
  const matcher =
    /\$\$([\s\S]+?)\$\$|(?<!\\)\$([^$\n]+?)(?<!\\)\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|<%%\s*image\b[\s\S]*?%%>/gi;
  for (const match of source.matchAll(matcher)) {
    output += escapeHtml(source.slice(cursor, match.index)).replaceAll(
      "\n",
      "<br>",
    );
    const math = match[1] ?? match[2] ?? match[3] ?? match[4];
    if (math !== undefined) {
      try {
        output += katex.renderToString(math, {
          displayMode: match[1] !== undefined || match[3] !== undefined,
          throwOnError: false,
          strict: false,
          trust: false,
        });
      } catch {
        output += `<code>${escapeHtml(match[0])}</code>`;
      }
    }
    cursor = Number(match.index) + match[0].length;
  }
  output += escapeHtml(source.slice(cursor)).replaceAll("\n", "<br>");
  return output;
}
