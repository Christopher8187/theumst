import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = relativePath => readFileSync(join(root, relativePath), "utf8");

const style = read("src/style.css");
const app = read("src/App.vue");
const studyView = read("src/components/StudyView.vue");
const graphView = read("src/components/KnowledgeGraph.vue");
const contentsView = read("src/components/ContentsTree.vue");
const imagePanel = read("src/components/ImagePanel.vue");
const graphDomain = read("src/domain/graph.js");
const contentsDomain = read("src/domain/contents.js");
const studyApi = read("src/services/studyApi.js");
const i18n = read("src/i18n.js");

function literalTemplateText(source) {
  const template = source.match(/<template>([\s\S]*?)<\/template>/)?.[1] || "";
  return template.replace(/<[^>]+>/g, " ").replace(/\{\{[\s\S]*?\}\}/g, " ");
}

const translatedValues = [...i18n.matchAll(/:\s*"((?:\\.|[^"\\])*)"/g)].map(match => match[1]).join(" ");
const literalUiText = [studyView, graphView, contentsView, imagePanel]
  .map(literalTemplateText)
  .join(" ");
const learnerCopy = `${translatedValues} ${literalUiText}`;
const learnerInfrastructureTerms = /\b(?:embedding|embeddings|vector|vectors|API|node|nodes|edge|edges|DAG)\b|graph revision|嵌入|埋め込み|节点|ノード/iu;

const checks = [];
const check = (name, condition, detail) => checks.push({ name, condition: Boolean(condition), detail });

check("16px root reading size", /:root\s*\{[\s\S]*?font-size:\s*16px\s*;/m.test(style), "The root comfort layer must establish a 16px base.");
check("dark overscroll canvas", /html,[\s\S]*?#app\s*\{[\s\S]*?overscroll-behavior:\s*none/m.test(style), "html/body/#app must keep overscroll on the navy canvas.");
check("visible keyboard focus", /:focus-visible[\s\S]*?outline:\s*3px\s+solid\s+var\(--focus\)/m.test(style), "Interactive controls need a high-contrast focus ring.");
check("reduced motion", /@media\s*\(prefers-reduced-motion:\s*reduce\)/m.test(style), "Animation and transition fallbacks are required.");
check("bounded Contents viewport", /\.contents-tree\.contents-level-1\s*\{[\s\S]*?max-height:[\s\S]*?overflow:\s*auto/m.test(style), "Expanded Contents must scroll inside a bounded region.");
check("bounded graph paint", /(?:\.graph-viewport|\.semantic-graph-viewport|\.graph-canvas)[\s\S]*?contain:\s*layout\s+paint/m.test(style), "The focused graph viewport must bound layout and paint.");
check("usable image close target", /\.image-panel header button,[\s\S]*?width:\s*44px;[\s\S]*?height:\s*44px/m.test(style), "Image and side-panel close buttons must be at least 44px.");
check("responsive tablet breakpoint", /@media\s*\(max-width:\s*900px\)/m.test(style), "Tablet layouts need an explicit bounded-stack breakpoint.");
check("responsive phone breakpoint", /@media\s*\(max-width:\s*480px\)/m.test(style), "390px layouts need an explicit narrow-screen pass.");
check("no order-coupled card style", !/\.realm-card:nth-child|\.graph-node:nth-of-type/.test(style), "Visual placement must not depend on record order.");
check("learner copy hides infrastructure", !learnerInfrastructureTerms.test(learnerCopy), "Learners should see items, relationships, and similarity—not implementation terms such as embeddings, vectors, APIs, nodes, edges, DAGs, or graph revisions.");

check("Contents hierarchy uses parent metadata", /parent_section/.test(contentsDomain) && /parent\.children\.push\(item\)/.test(contentsDomain) && /flattenVisibleContents/.test(contentsView), "Contents must derive depth from real parent metadata rather than source proximity.");
check("collapsed Contents branches stay out of DOM", /expanded\.has\(key\)[\s\S]*?flattenVisibleContents\(item\.children/m.test(contentsDomain) && /visibleRows[\s\S]*?slice\(pageStart\.value,\s*pageEnd\.value\)/m.test(contentsView), "Only expanded descendants in the bounded visible window may enter the DOM.");
check("Contents controls expose tree state", /role="treeitem"/.test(contentsView) && /:aria-level=/.test(contentsView) && /:aria-expanded=/.test(contentsView) && /:aria-current=/.test(contentsView), "Expansion, depth, and current location must be available to assistive technology.");

check("Crystallize control absent", !/crystallize/i.test(studyView), "The unavailable Crystallize feature must not be interactive or presented as working.");
check("exact Cluster action", /\{\{\s*t\.cluster\s*\}\}/.test(studyView), "The embedding-neighbour action must use Christopher's exact Cluster label.");
check("canonical Similar endpoint", /\/api\/demo\/knowledge\/\$\{knowledgeId\}\/similar\?\$\{params\}/.test(studyApi), "Similarity must use the frozen top-k endpoint.");
check("legacy Crystallize endpoint absent", !/\/api\/demo\/crystallize/.test(app + studyApi), "No runtime call may target the removed Crystallize endpoint.");
check("Similarity excludes selected item", /(?:Number\(result\.knowledge_id\)\s*!==\s*Number\(knowledgeId\)|key\s*===\s*selectedKey|String\(result\.knowledge_id\)\s*!==\s*selectedKey)/.test(studyApi), "The selected item cannot appear in its own neighbours.");
check("Similarity sorts descending", /sort\s*\(\s*\((?:a|left),\s*(?:b|right)\)\s*=>\s*(?:b|right)\.similarity_score\s*-\s*(?:a|left)\.similarity_score\s*\)/.test(studyApi), "Top-k results must be displayed from highest to lowest similarity.");

check("canonical focused graph endpoint", /\/api\/demo\/grimoires\/\$\{grimoireId\}\/graph\?\$\{params\}/.test(studyApi), "The graph must come from the frozen focused-slice endpoint.");
check("focused graph bounds", /ancestor_depth/.test(studyApi) && /descendant_depth/.test(studyApi) && /limit:\s*"150"/.test(studyApi), "The graph request must carry depth and hard-limit bounds.");
check("reader index cached once per book", /const\s+studyCache\s*=\s*new\s+Map\(\)/.test(app) && /studyCache\.get\(cacheKey\)[\s\S]*?if\s*\(!data\)[\s\S]*?demoFetch\(`\/api\/demo\/grimoires\/\$\{bookId\}\/knowledge`\)[\s\S]*?studyCache\.set\(cacheKey,\s*data\)/m.test(app), "The permitted static reader index must be fetched at most once per grimoire in a demo session.");
check("graph consumes focused slice only", /props\.graph/.test(graphView) && !/source_order|props\.nodes|relationCounts/.test(graphView), "KnowledgeGraph must render only the canonical focused graph slice, never reader-index order or type-derived lanes.");
check("assessment role protected", /ASSESSMENT_TYPES[\s\S]*?return\s+"assessment"/m.test(graphDomain), "Exercise nodes must be classified as assessment, never backbone.");
check("fragment role protected", /FRAGMENT_TYPES[\s\S]*?return\s+"fragment"/m.test(graphDomain), "JAS nodes must be classified as fragments, never backbone.");
check("graph consumes canonical projection edges", /source_knowledge_id/.test(graphDomain) && /target_knowledge_id/.test(graphDomain) && /relation_type/.test(graphDomain) && /book_order_v1/.test(graphDomain), "The client must preserve the server-supplied book_order_v1 projection fields without manufacturing edges.");
check("graph has deliberate empty state", /(?:edge-empty-state|graph-(?:empty|unavailable))/.test(graphView), "An edge-empty or unavailable focused graph needs an honest visible state.");

check("image close is named", /aria-label="Close image"/.test(imagePanel), "The image panel close control must have an accessible name.");
check("image alt text is meaningful", /:alt=/.test(imagePanel), "Book images must expose contextual alternative text.");

const failures = checks.filter(item => !item.condition);
for (const item of checks) {
  const marker = item.condition ? "PASS" : "FAIL";
  console.log(`${marker}  ${item.name}`);
  if (!item.condition) console.log(`      ${item.detail}`);
}

console.log(`\n${checks.length - failures.length}/${checks.length} static demo contracts passed.`);
if (failures.length) process.exitCode = 1;
