import { books as entranceBooks, type SampleBook, type BookSection } from '../books';
import analysisSource from './study-fixtures-analysis.json';
import hexagonUrl from './assets/symmetry-hexagon.svg';
import lightPathUrl from './assets/light-travel.svg';
import integralCurveUrl from './assets/analysis-quadratic.svg';

export type StudyMode = 'text' | 'questions';
export interface StudyImage {
  source_image_id: string;
  semantic_context_name: string;
  url: string;
  metadata: { context: string };
}
export interface StudyNode {
  knowledge_id: number;
  grimoire_id: number;
  section_id: number;
  type: string;
  label: string;
  statement: string;
  working: string;
  completed: boolean;
  breadcrumbs: { section_id: number; number: string; name: string }[];
  images: StudyImage[];
  knowledge_crystal_id?: number;
  is_default_in_crystal?: boolean;
}
export interface StudyEdge {
  source_knowledge_id: number;
  target_knowledge_id: number;
  relation_type: 'dependency';
}
export interface StudyFixture {
  sample: SampleBook;
  book: { grimoire_id: number; title: string; source_key: string; publisher?: string; version?: string };
  nodes: StudyNode[];
  sections: BookSection[];
  edges: StudyEdge[];
}
export interface StudyResult extends StudyNode {
  book_title: string;
  fixture_reason: string;
  similarity_score?: number;
  fixture_score_kind?: 'illustrative-only';
}

export const sampleBookIds: Record<string, number> = { analysis: 1, symmetry: 2, light: 3, companion: 4 };

function image(id: string, title: string, url: string, context: string): StudyImage {
  return { source_image_id: id, semantic_context_name: title, url, metadata: { context } };
}

const hexagon = image('symmetry-hexagon', 'Six rotations of a regular hexagon',
  hexagonUrl,
  'Authored diagram for this local example: a regular hexagon, three opposite-vertex axes and a 60-degree rotation. The three opposite-side axes are not drawn.');
const lightPath = image('light-travel', 'A light signal travelling through a vacuum',
  lightPathUrl,
  'Authored schematic: a source on the left, a receiver on the right and the path between them. The wave is illustrative; its wavelength and the drawing are not to scale.');
const integralCurve = image('analysis-quadratic', 'Rectangle approximations for a quadratic',
  integralCurveUrl,
  'Authored illustration of the supplied quadratic integration exercise. Rectangles suggest a left-endpoint approximation on [0,1]; the axes are schematic.');

function ancestry(sectionId: number, sections: BookSection[]) {
  const result: StudyNode['breadcrumbs'] = [];
  let current = sections.find(section => section.section_id === sectionId);
  const seen = new Set<number>();
  while (current && !seen.has(current.section_id)) {
    seen.add(current.section_id);
    if (!current.is_book_root) result.unshift({ section_id: current.section_id, number: current.section_number, name: current.section_name });
    current = sections.find(section => section.section_id === current?.parent_section);
  }
  return result;
}

function analysisFixture(sample: SampleBook): StudyFixture {
  // The frozen source below is extracted from section-atlas.html by the same
  // declaration boundary used in backend/examples/real-analysis-demo/build_archive.py.
  // Preserve its 36 objects, 42 authored relations and full 24-section hierarchy.
  const entries = Object.entries(analysisSource.hierarchy);
  const sectionIds = new Map(entries.map(([key], position) => [key, position + 1]));
  const sections = entries.map(([key, section]) => {
    const parts = section.name.split(' · ');
    return { section_id: sectionIds.get(key)!, parent_section: section.parent ? sectionIds.get(section.parent)! : null,
      section_number: parts.length > 1 ? parts[0] : '0', section_name: parts.at(-1)!, is_book_root: key === 'book' };
  });
  const workings: Record<number, string> = {
    13: 'Use uniform continuity from item 4, then apply the integrability criterion from item 12. These are two separate incoming dependencies.',
    15: 'Compute the sum of the first n squares, divide by the appropriate power of n, then take the limit.',
  };
  const nodes = analysisSource.nodes.map(node => ({
    knowledge_id: node.id, grimoire_id: 1, section_id: sectionIds.get(node.section)!, type: node.type,
    label: node.title, statement: `${node.text}\n\n$$${node.math}$$`, working: workings[node.id] || '',
    completed: node.id <= (sample.completed || 0), breadcrumbs: ancestry(sectionIds.get(node.section)!, sections),
    images: node.id === 15 ? [integralCurve] : [],
  }));
  return { sample: { ...sample, contents: sections }, book: { grimoire_id: 1, title: sample.title, source_key: 'section-atlas-sample-v1', publisher: sample.publisher, version: sample.version },
    sections, nodes, edges: analysisSource.deps.map(([a, b]) => ({ source_knowledge_id: a, target_knowledge_id: b, relation_type: 'dependency' })) };
}

function miniatureFixture(sample: SampleBook): StudyFixture {
  const bookId = sampleBookIds[sample.id];
  const sections = (sample.contents || []).map(section => ({ ...section }));
  const symmetryWorkings = [
    'Distances between every pair of points stay unchanged, and every transformed point is still in the original figure. Both conditions matter: simply preserving distances does not guarantee that a transformation maps this particular figure onto itself.',
    'There are n equally spaced vertices on a full turn. Moving each vertex k places around the centre gives an angle of k times one nth of a turn.',
    'Substitute n = 6 into the rotation rule. Three reflection axes join opposite vertices; another three join the midpoints of opposite sides.',
    sample.passages[3].answer || '',
  ];
  const lightWorkings = [
    'The stated exact value fixes the metre through the speed of light in vacuum. The rounded value used in these examples has three significant figures.',
    'Rearrange distance = speed × time by dividing both sides by c. Units check: metres divided by metres per second gives seconds.',
    'Multiply speed by elapsed time. The seconds cancel. Divide the result in metres by 1,000 to express it in kilometres.',
    sample.passages[3].answer || '',
  ];
  const nodes = sample.passages.map((passage, position) => {
    const sectionId = 110 + position;
    return { knowledge_id: bookId * 100 + position + 1, grimoire_id: bookId, section_id: sectionId,
      type: ['definition', sample.id === 'symmetry' ? 'theorem' : 'claim', 'example', 'exercise'][position],
      label: passage.title, statement: passage.text + (passage.math ? `\n\n$$${passage.math}$$` : ''),
      working: (sample.id === 'symmetry' ? symmetryWorkings : lightWorkings)[position],
      completed: position < (sample.completed || 0), breadcrumbs: ancestry(sectionId, sections),
      images: sample.id === 'symmetry' && position === 2 ? [hexagon] : sample.id === 'light' && position === 1 ? [lightPath] : [],
    };
  });
  return { sample: { ...sample }, book: { grimoire_id: bookId, title: sample.title, source_key: `wisdom-${sample.id}-v1` }, sections, nodes,
    edges: [[0, 1], [1, 2], [1, 3]].map(([a, b]) => ({ source_knowledge_id: nodes[a].knowledge_id, target_knowledge_id: nodes[b].knowledge_id, relation_type: 'dependency' })) };
}

export function createStudyFixtures(seedBooks: readonly SampleBook[] = entranceBooks): Record<number, StudyFixture> {
  const seed = new Map(seedBooks.map(book => [book.id, book]));
  const fixtures = Object.fromEntries(entranceBooks.map(original => {
    const sample = { ...original, ...(seed.get(original.id) || {}) };
    const fixture = sample.id === 'analysis' ? analysisFixture(sample) : miniatureFixture(sample);
    return [fixture.book.grimoire_id, fixture];
  })) as Record<number, StudyFixture>;
  // Two intentionally repeated statements provide a finite, honest example of
  // same-crystal results. The companion is reached through discovery only.
  const sections: BookSection[] = [{ section_id: 401, parent_section: null, section_number: '1', section_name: 'Shared definitions' }];
  const copied = [fixtures[2].nodes[0], fixtures[3].nodes[0]].map((source, position) => {
    source.knowledge_crystal_id = 501 + position;
    source.is_default_in_crystal = true;
    return { ...source, knowledge_id: 401 + position, grimoire_id: 4, section_id: 401, completed: false,
      working: 'This companion repeats the original definition verbatim so the prototype can demonstrate a second source for the same statement.',
      breadcrumbs: ancestry(401, sections), images: [], is_default_in_crystal: false };
  });
  fixtures[4] = {
    sample: { id: 'companion', title: 'Shared Definitions · Companion', short: 'Companion', subject: 'Local example', color: '#718692', symbol: '↔', count: 2, edition: 'Local example', summary: 'Two explicitly repeated definitions for testing cross-book navigation and same-statement discovery.', passages: [], contents: sections, completed: 0 },
    book: { grimoire_id: 4, title: 'Shared Definitions · Companion', source_key: 'wisdom-shared-definitions-v1' }, sections, nodes: copied, edges: [],
  };
  return fixtures;
}

export function discoveryExamples(fixtures: Record<number, StudyFixture>, source: StudyNode, kind: string): StudyResult[] {
  const all = Object.values(fixtures).flatMap(fixture => fixture.nodes);
  let matches: StudyNode[];
  if (kind === 'crystallize') {
    matches = source.knowledge_crystal_id ? all.filter(node => node.knowledge_crystal_id === source.knowledge_crystal_id) : [];
  } else {
    const fixture = fixtures[source.grimoire_id];
    const linkedIds = new Set(fixture.edges.flatMap(edge => edge.source_knowledge_id === source.knowledge_id ? [edge.target_knowledge_id] : edge.target_knowledge_id === source.knowledge_id ? [edge.source_knowledge_id] : []));
    const handPicked: [number, number][] = [[201, 401], [301, 402], [19, 302], [20, 302]];
    for (const [a, b] of handPicked) { if (a === source.knowledge_id) linkedIds.add(b); if (b === source.knowledge_id) linkedIds.add(a); }
    matches = all.filter(node => linkedIds.has(node.knowledge_id));
  }
  return matches.map(node => ({ ...node, book_title: fixtures[node.grimoire_id].book.title,
    fixture_reason: kind === 'crystallize' ? 'Authored equal statement' : 'Hand-picked local reading example',
    // These three deliberately fixed display values exercise the former UI.
    // They are not measured semantic scores; the prototype labels them as such.
    ...(kind === 'crystallize' ? {} : { similarity_score: node.knowledge_crystal_id && node.knowledge_crystal_id === source.knowledge_crystal_id ? .98 : node.grimoire_id === source.grimoire_id ? .74 : .68, fixture_score_kind: 'illustrative-only' as const }),
  })).sort((a, b) => kind === 'crystallize' ? Number(!!b.is_default_in_crystal) - Number(!!a.is_default_in_crystal) : (b.similarity_score || 0) - (a.similarity_score || 0) || a.knowledge_id - b.knowledge_id);
}
