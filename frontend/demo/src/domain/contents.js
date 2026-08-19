function integer(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function parentSectionId(section = {}) {
  return integer(
    section.parent_section
      ?? section.parent_section_id
      ?? section.parent_id
      ?? section.source_metadata?.parent_section
  );
}

export function contentsItemKey(item = {}) {
  return String(item.tree_key ?? (integer(item.section_id) == null ? "" : `section:${integer(item.section_id)}`));
}

/**
 * Build a hierarchy exclusively from the section identifiers and parent metadata
 * supplied by the API. Input order is retained within each sibling group because
 * the book endpoint already applies the source's deliberate section ordering.
 */
export function buildContentsTree(sections = []) {
  const source = Array.isArray(sections) ? sections : [];
  const items = source.map((section, sourceIndex) => {
    const sectionId = integer(section?.section_id);
    return {
      ...section,
      section_id: sectionId,
      parent_section: parentSectionId(section),
      source_index: sourceIndex,
      tree_key: sectionId == null ? `unidentified:${sourceIndex}` : `section:${sectionId}:${sourceIndex}`,
      children: []
    };
  });

  // A duplicated identifier is ambiguous. Keep every row visible, but do not use
  // an ambiguous identifier to manufacture a parent/child relationship.
  const idCounts = new Map();
  for (const item of items) {
    if (item.section_id != null) idCounts.set(item.section_id, (idCounts.get(item.section_id) || 0) + 1);
  }
  const byId = new Map(
    items
      .filter(item => item.section_id != null && idCounts.get(item.section_id) === 1)
      .map(item => [item.section_id, item])
  );

  function safeParent(item) {
    if (item.parent_section == null || item.parent_section === item.section_id) return null;
    const parent = byId.get(item.parent_section);
    if (!parent) return null;

    const seen = new Set([item.section_id]);
    let cursor = parent;
    while (cursor) {
      if (cursor.section_id == null || seen.has(cursor.section_id)) return null;
      seen.add(cursor.section_id);
      cursor = cursor.parent_section == null ? null : byId.get(cursor.parent_section);
    }
    return parent;
  }

  const roots = [];
  for (const item of items) {
    const parent = safeParent(item);
    if (parent) parent.children.push(item);
    else roots.push(item);
  }
  return roots;
}

export function findSectionPath(tree = [], sectionId) {
  const target = integer(sectionId);
  if (target == null) return [];

  function visit(items, path) {
    for (const item of items) {
      const nextPath = [...path, item];
      if (item.section_id === target) return nextPath;
      const found = visit(item.children || [], nextPath);
      if (found.length) return found;
    }
    return [];
  }

  return visit(Array.isArray(tree) ? tree : [], []);
}

export function defaultExpandedContents(tree = [], currentSectionId = null) {
  const roots = Array.isArray(tree) ? tree : [];
  const expanded = new Set();
  const currentPath = findSectionPath(roots, currentSectionId);

  // Reveal the selected section and its context, but leave unrelated chapters
  // collapsed. A single synthetic/book root is opened to avoid a one-row TOC.
  for (const item of currentPath.slice(0, -1)) expanded.add(contentsItemKey(item));
  if (currentPath.length === 0 && roots.length === 1 && roots[0].children?.length) {
    expanded.add(contentsItemKey(roots[0]));
  }
  return expanded;
}

export function flattenVisibleContents(tree = [], expanded = new Set(), depth = 1, parentKey = null) {
  const rows = [];
  for (const item of Array.isArray(tree) ? tree : []) {
    const key = contentsItemKey(item);
    rows.push({ item, key, depth, parentKey });
    if (item.children?.length && (expanded.has(key) || expanded.has(item.section_id))) {
      rows.push(...flattenVisibleContents(item.children, expanded, depth + 1, key));
    }
  }
  return rows;
}

export function visibleContentsCount(tree = [], expanded = new Set()) {
  return flattenVisibleContents(tree, expanded).length;
}
