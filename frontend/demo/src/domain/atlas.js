// Grouping and collision routing adapted from the accepted Section Atlas.
// Inputs use the complete available reader order; ordinal IDs are drawing-local.
export const ATLAS_NODE_LIMIT = 24;
export const ATLAS_EDGE_LIMIT = 72;

export function buildAtlas(
  objects,
  sections,
  relations,
  selectedId,
  options = {},
) {
  const LIMIT = options.limit ?? ATLAS_NODE_LIMIT,
    EDGE_LIMIT = ATLAS_EDGE_LIMIT,
    W = 160,
    H = 64;
  const hierarchy = { book: { name: "", parent: null } };
  const bySection = new Map(sections.map((s) => [String(s.section_id), s]));
  for (const s of sections)
    hierarchy[String(s.section_id)] = {
      name: [s.section_number, s.section_name].filter(Boolean).join(" · "),
      parent: bySection.has(String(s.parent_section))
        ? String(s.parent_section)
        : "book",
    };
  // Publisher root sections stand for the whole book, not a direct subsection.
  const roots = sections.filter(
    (section) => !bySection.has(String(section.parent_section)),
  );
  for (const section of roots) {
    const id = String(section.section_id);
    if (
      section.is_book_root === true ||
      (["", "0"].includes(String(section.section_number ?? "")) &&
        sections.some((child) => String(child.parent_section) === id))
    ) {
      for (const entry of Object.values(hierarchy))
        if (entry.parent === id) entry.parent = "book";
    }
  }
  const nodes = objects.map((n, i) => {
    const section = String(n.section_id ?? "unsectioned");
    if (!hierarchy[section])
      hierarchy[section] = {
        name: n.breadcrumbs?.at(-1)?.name || "",
        parent: "book",
      };
    return {
      ...n,
      id: i + 1,
      section,
      title: n.label || "",
      completed: !!n.completed,
    };
  });
  const ordinal = new Map(nodes.map((n) => [String(n.knowledge_id), n.id]));
  const deps = relations
    .map((e) => [
      ordinal.get(String(e.source_knowledge_id)),
      ordinal.get(String(e.target_knowledge_id)),
    ])
    .filter(([a, b]) => a && b && a !== b);
  const adjacency = new Map(nodes.map((n) => [n.id, []]));
  deps.forEach(([a, b]) => {
    adjacency.get(a).push(b);
    adjacency.get(b).push(a);
  });
  if (!nodes.length)
    return {
      placed: [],
      parents: [],
      tiles: [],
      badges: [],
      edges: [],
      width: 800,
      height: 400,
      candidates: 0,
      omitted: 0,
    };
  function ancestry(section) {
    const a = [];
    const seen = new Set();
    while (section && hierarchy[section] && !seen.has(section)) {
      seen.add(section);
      a.unshift(section);
      section = hierarchy[section].parent;
    }
    return a;
  }
  function direct(section) {
    return ancestry(section)[1] || section;
  }
  function nearby(s) {
    const d = new Map([[s.current, 0]]),
      q = [s.current];
    let scanned = 0;
    for (let i = 0; i < q.length && i < nodes.length; i++) {
      const at = q[i];
      if (d.get(at) >= s.dep) continue;
      for (const next of adjacency.get(at)) {
        scanned++;
        if (!d.has(next)) {
          d.set(next, d.get(at) + 1);
          q.push(next);
        }
      }
    }
    const candidates = nodes.filter((n) => {
      const b = Math.abs(n.id - s.current) <= s.book,
        p = (d.get(n.id) ?? Infinity) <= s.dep;
      return s.combine === "either" ? b || p : b && p;
    });
    const priority = (n) =>
      n.id === s.current
        ? -10
        : Math.min(
            Math.abs(n.id - s.current) / Math.max(1, s.book),
            (d.get(n.id) ?? 100) / Math.max(1, s.dep),
          );
    const shown = candidates
      .sort(
        (a, b) =>
          priority(a) - priority(b) ||
          Math.abs(a.id - s.current) - Math.abs(b.id - s.current) ||
          a.id - b.id,
      )
      .slice(0, LIMIT)
      .sort((a, b) => a.id - b.id);
    return { shown, candidates: candidates.length, distances: d, scanned };
  }

  function sectionEdges(ids, owner) {
    const allowed = new Set(ids),
      result = new Map();
    for (const [a, b] of deps) {
      const x = owner(nodes[a - 1]),
        y = owner(nodes[b - 1]);
      if (x !== y && allowed.has(x) && allowed.has(y))
        result.set(x + ">" + y, [x, y]);
    }
    return [...result.values()];
  }
  // Two deterministic box layouts. Tarjan condensation handles cycles introduced by grouping.
  function packBoxes(items, edges, t, columns) {
    if (!items.length) return [];
    const order = new Map(items.map((b, i) => [b.id, i])),
      byId = new Map(items.map((b) => [b.id, b])),
      adj = new Map(items.map((b) => [b.id, []]));
    edges.forEach(([a, b]) => adj.get(a)?.push(b));
    const number = new Map(),
      low = new Map(),
      stack = [],
      active = new Set(),
      components = [];
    let serial = 0;
    function visit(id) {
      number.set(id, serial);
      low.set(id, serial++);
      stack.push(id);
      active.add(id);
      for (const next of adj.get(id)) {
        if (!number.has(next)) {
          visit(next);
          low.set(id, Math.min(low.get(id), low.get(next)));
        } else if (active.has(next))
          low.set(id, Math.min(low.get(id), number.get(next)));
      }
      if (low.get(id) === number.get(id)) {
        const part = [];
        let next;
        do {
          next = stack.pop();
          active.delete(next);
          part.push(next);
        } while (next !== id);
        components.push(part);
      }
    }
    items.forEach((b) => {
      if (!number.has(b.id)) visit(b.id);
    });
    const component = new Map();
    components.forEach((part, i) => part.forEach((id) => component.set(id, i)));
    const links = new Map();
    edges.forEach(([a, b]) => {
      const x = component.get(a),
        y = component.get(b);
      if (x !== y) links.set(x + ">" + y, [x, y]);
    });
    const ce = [...links.values()],
      degree = components.map((_, i) => ce.filter((e) => e[1] === i).length),
      ranks = components.map(() => 0),
      queue = degree.flatMap((n, i) => (n === 0 ? [i] : []));
    for (let i = 0; i < queue.length; i++)
      for (const [a, b] of ce)
        if (a === queue[i]) {
          ranks[b] = Math.max(ranks[b], ranks[a] + 1);
          if (--degree[b] === 0) queue.push(b);
        }
    const layers = [];
    items.forEach((b) =>
      (layers[ranks[component.get(b.id)]] ??= []).push(b.id),
    );
    const slot = new Map();
    const refresh = () =>
      layers.forEach((row) =>
        row.forEach((id, i) => slot.set(id, i - (row.length - 1) / 2)),
      );
    refresh();
    for (let pass = 0; pass < 4; pass++) {
      const down = pass % 2 === 0;
      for (const row of down ? layers : [...layers].reverse()) {
        const score = (id) => {
          const near = edges
            .filter((e) => e[down ? 1 : 0] === id)
            .map((e) => slot.get(e[down ? 0 : 1]));
          return near.length
            ? near.reduce((a, b) => a + b, 0) / near.length
            : slot.get(id);
        };
        row.sort((a, b) => score(a) - score(b) || order.get(a) - order.get(b));
        refresh();
      }
    }
    const gap = 76,
      colGap = 140,
      colWidth = Math.max(...items.map((b) => b.w)),
      snake = new Map();
    let sy = 0;
    for (let start = 0; start < items.length; start += columns) {
      const row = items.slice(start, start + columns),
        rowNumber = Math.floor(start / columns);
      row.forEach((b, i) => {
        const col = rowNumber % 2 ? columns - 1 - i : i;
        snake.set(b.id, {
          x: col * (colWidth + colGap),
          y: sy,
          row: rowNumber,
        });
      });
      sy += Math.max(...row.map((b) => b.h)) + gap;
    }
    const layered = new Map();
    let dy = 0;
    for (const row of layers) {
      for (let start = 0; start < row.length; start += columns) {
        const slice = row.slice(start, start + columns),
          width =
            slice.reduce((sum, id) => sum + byId.get(id).w, 0) +
            colGap * (slice.length - 1);
        let x = ((colWidth + colGap) * columns - gap - width) / 2;
        slice.forEach((id) => {
          layered.set(id, { x, y: dy });
          x += byId.get(id).w + colGap;
        });
        dy += Math.max(...slice.map((id) => byId.get(id).h)) + gap;
      }
    }
    let result = items.map((b) => {
      const a = snake.get(b.id),
        d = layered.get(b.id);
      return {
        ...b,
        x: (t === 0 ? a : d).x,
        y: (t === 0 ? a : d).y,
        snakeRow: a.row,
        rank: ranks[component.get(b.id)],
        cyclic: components[component.get(b.id)].length > 1,
      };
    });
    const accepted = [];
    for (const b of [...result].sort(
      (a, b) => a.y - b.y || order.get(a.id) - order.get(b.id),
    )) {
      for (let pass = 0; pass < items.length; pass++) {
        const hit = accepted.filter(
          (a) =>
            b.x < a.x + a.w + 32 &&
            b.x + b.w + 32 > a.x &&
            b.y < a.y + a.h + 32 &&
            b.y + b.h + 32 > a.y,
        );
        if (!hit.length) break;
        b.y = Math.max(...hit.map((a) => a.y + a.h + 32));
      }
      accepted.push(b);
    }
    const minX = Math.min(...result.map((b) => b.x));
    return result.map((b) => ({ ...b, x: b.x - minX }));
  }
  function arrange(visible, blend) {
    const gaps = visible
      .slice(1)
      .flatMap((n, i) =>
        n.id > visible[i].id + 1
          ? [
              {
                a: visible[i].id,
                b: n.id,
                count: n.id - visible[i].id - 1,
                section: visible[i].section,
              },
            ]
          : [],
      );
    const active = new Set(
      visible.flatMap((n) => ancestry(n.section)).filter((id) => id !== "book"),
    );
    const children = new Map();
    for (const id of active) {
      const parent = active.has(hierarchy[id].parent)
        ? hierarchy[id].parent
        : "book";
      (children.get(parent) || children.set(parent, []).get(parent)).push(id);
    }
    const first = (id) =>
      Math.min(
        ...visible
          .filter((n) => ancestry(n.section).includes(id))
          .map((n) => n.id),
      );
    for (const list of children.values())
      list.sort((a, b) => first(a) - first(b));
    function build(id, seen = new Set()) {
      const members = visible.filter((n) => n.section === id),
        ownGaps = gaps.filter((g) => g.section === id);
      const leaf = {
        id,
        members,
        gaps: ownGaps,
        w: 216,
        h:
          88 +
          members.length * H +
          Math.max(0, members.length - 1) * 42 +
          24 +
          ownGaps.length * 48,
        leaf: true,
      };
      const next = (children.get(id) || []).filter((child) => !seen.has(child));
      if (!next.length) return leaf;
      const visited = new Set([...seen, id]);
      const boxes = next.map((child) => build(child, visited));
      if (members.length) {
        const own = id + ":own";
        hierarchy[own] = hierarchy[id];
        boxes.unshift({ ...leaf, id: own });
      }
      const owner = (n) => {
        if (n.section === id) return id + ":own";
        return next.find((child) => ancestry(n.section).includes(child));
      };
      const packed = packBoxes(
        boxes,
        sectionEdges(
          boxes.map((b) => b.id),
          owner,
        ),
        blend,
        3,
      );
      return {
        id,
        children: packed,
        w: Math.max(...packed.map((b) => b.x + b.w)) + 64,
        h: Math.max(...packed.map((b) => b.y + b.h)) + 124,
        leaf: false,
      };
    }
    const top = (children.get("book") || []).map((id) => build(id));
    // Malformed ancestry stays visible as a standalone group instead of recursing forever.
    if (!top.length)
      for (const id of new Set(visible.map((n) => n.section)))
        top.push({
          id,
          members: visible.filter((n) => n.section === id),
          w: 216,
          h: 112 + visible.filter((n) => n.section === id).length * 106,
          leaf: true,
        });
    const macro = packBoxes(
      top,
      sectionEdges(
        top.map((b) => b.id),
        (n) => direct(n.section),
      ),
      blend,
      2,
    );
    const tiles = [],
      parents = [],
      placed = [],
      headers = [];
    function place(box, x, y, depth) {
      const item = { ...box, x, y, depth };
      headers.push({ l: x + 13, r: x + box.w - 13, t: y + 12, b: y + 50 });
      if (box.leaf) {
        tiles.push(item);
        box.members.forEach((n, i) =>
          placed.push({
            ...n,
            x: x + 28,
            y:
              y +
              88 +
              i * (H + 42) +
              (box.gaps || []).filter((g) => g.b <= n.id).length * 48,
            rank: box.rank,
          }),
        );
      } else {
        parents.push(item);
        for (const child of box.children)
          place(child, x + 32 + child.x, y + 92 + child.y, depth + 1);
      }
    }
    for (const box of macro) place(box, box.x + 180, box.y + 72, 0);
    return {
      placed: placed.sort((a, b) => a.id - b.id),
      tiles,
      parents,
      gaps,
      badges: [],
      obstacles: headers,
      width: Math.max(...macro.map((b) => b.x + b.w)) + 280,
      height: Math.max(...macro.map((b) => b.y + b.h)) + 172,
    };
  }
  function routeAll(placed, edges, extraObstacles = []) {
    const byId = new Map(placed.map((n) => [n.id, n])),
      out = new Map(),
      inc = new Map();
    edges.forEach((e) => {
      (out.get(e.a) || out.set(e.a, []).get(e.a)).push(e);
      (inc.get(e.b) || inc.set(e.b, []).get(e.b)).push(e);
    });
    const xValues = new Set(),
      yValues = new Set([24]);
    const obstacles = [
      ...placed.map((n) => ({
        l: n.x - 7,
        r: n.x + W + 7,
        t: n.y - 7,
        b: n.y + H + 7,
      })),
      ...extraObstacles,
    ];
    for (const o of extraObstacles) {
      xValues.add(o.l - 12);
      xValues.add(o.r + 12);
      yValues.add(o.t - 12);
      yValues.add(o.b + 12);
    }
    for (const n of placed) {
      xValues.add(n.x - 24);
      xValues.add(n.x + W + 24);
      yValues.add(n.y - 32);
      yValues.add(n.y + H + 32);
    }

    const ports = new Map();
    for (const e of edges) {
      const a = byId.get(e.a),
        b = byId.get(e.b),
        dx = b.x - a.x,
        dy = b.y - a.y;
      const horizontal = Math.abs(dx) > Math.abs(dy) * 1.15;
      e.fromSide = horizontal
        ? dx > 0
          ? "right"
          : "left"
        : dy >= 0
          ? "bottom"
          : "top";
      e.toSide = { right: "left", left: "right", bottom: "top", top: "bottom" }[
        e.fromSide
      ];
      for (const [id, side, end] of [
        [e.a, e.fromSide, "s"],
        [e.b, e.toSide, "t"],
      ]) {
        const key = id + ":" + side;
        (ports.get(key) || ports.set(key, []).get(key)).push({
          e,
          end,
          id,
          side,
        });
      }
    }
    for (const bucket of ports.values())
      bucket.forEach((p, i) => {
        const n = byId.get(p.id),
          horizontal = ["left", "right"].includes(p.side),
          length = horizontal ? H : W,
          spacing = Math.min(
            16,
            (length - 20) / Math.max(1, bucket.length - 1),
          ),
          offset = (i - (bucket.length - 1) / 2) * spacing;
        let x = n.x + W / 2,
          y = n.y + H / 2,
          dx = 0,
          dy = 0;
        if (p.side === "left") {
          x = n.x;
          y += offset;
          dx = -18;
        } else if (p.side === "right") {
          x = n.x + W;
          y += offset;
          dx = 18;
        } else if (p.side === "top") {
          x += offset;
          y = n.y;
          dy = -18;
        } else {
          x += offset;
          y = n.y + H;
          dy = 18;
        }
        p.e[p.end === "s" ? "start" : "end"] = { x, y };
        p.e[p.end] = { x: x + dx, y: y + dy };
        xValues.add(x + dx);
        yValues.add(y + dy);
        if (horizontal) {
          xValues.add(x + dx - 8);
          xValues.add(x + dx + 8);
        } else {
          yValues.add(y + dy - 8);
          yValues.add(y + dy + 8);
        }
      });
    const maxX = Math.max(...placed.map((n) => n.x + W)),
      maxY = Math.max(...placed.map((n) => n.y + H));
    for (let i = 0; i < 12; i++) {
      xValues.add(Math.min(...placed.map((n) => n.x)) - 40 - i * 9);
      xValues.add(maxX + 40 + i * 9);
      yValues.add(32 + i * 2);
      yValues.add(maxY + 40 + i * 4);
    }
    const xs = [...xValues].sort((a, b) => a - b),
      ys = [...yValues].sort((a, b) => a - b),
      nx = xs.length,
      N = nx * ys.length;
    const xAt = new Map(xs.map((v, i) => [v, i])),
      yAt = new Map(ys.map((v, i) => [v, i]));
    const blocked = new Uint8Array(N),
      links = new Uint8Array(N);
    for (let y = 0; y < ys.length; y++)
      for (let x = 0; x < nx; x++) {
        const k = y * nx + x;
        if (
          obstacles.some(
            (o) => xs[x] > o.l && xs[x] < o.r && ys[y] > o.t && ys[y] < o.b,
          )
        )
          blocked[k] = 1;
      }
    const crossRect = (x1, y1, x2, y2) =>
      obstacles.some((o) =>
        x1 === x2
          ? x1 > o.l &&
            x1 < o.r &&
            Math.max(y1, y2) > o.t &&
            Math.min(y1, y2) < o.b
          : y1 > o.t &&
            y1 < o.b &&
            Math.max(x1, x2) > o.l &&
            Math.min(x1, x2) < o.r,
      );
    for (let y = 0; y < ys.length; y++)
      for (let x = 0; x < nx; x++) {
        const k = y * nx + x;
        if (blocked[k]) continue;
        if (
          x + 1 < nx &&
          !blocked[k + 1] &&
          !crossRect(xs[x], ys[y], xs[x + 1], ys[y])
        ) {
          links[k] |= 1;
          links[k + 1] |= 2;
        }
        if (
          y + 1 < ys.length &&
          !blocked[k + nx] &&
          !crossRect(xs[x], ys[y], xs[x], ys[y + 1])
        ) {
          links[k] |= 4;
          links[k + nx] |= 8;
        }
      }
    const occupied = new Set(),
      used = new Uint8Array(N),
      turns = new Uint8Array(N);
    const key = (a, b) => (a < b ? a * N + b : b * N + a);
    const portCells = new Set(
      edges.flatMap((e) => [
        yAt.get(e.s.y) * nx + xAt.get(e.s.x),
        yAt.get(e.t.y) * nx + xAt.get(e.t.x),
      ]),
    );
    function find(e) {
      const start = yAt.get(e.s.y) * nx + xAt.get(e.s.x),
        target = yAt.get(e.t.y) * nx + xAt.get(e.t.x),
        cost = new Float64Array(N * 3);
      cost.fill(Infinity);
      const prev = new Int32Array(N * 3);
      prev.fill(-1);
      const heap = [];
      const push = (id, v) => {
        let i = heap.length;
        heap.push([id, v]);
        while (i) {
          const p = (i - 1) >> 1;
          if (heap[p][1] <= v) break;
          heap[i] = heap[p];
          i = p;
        }
        heap[i] = [id, v];
      };
      const pop = () => {
        const root = heap[0],
          last = heap.pop();
        if (heap.length) {
          let i = 0;
          while (i * 2 + 1 < heap.length) {
            let c = i * 2 + 1;
            if (c + 1 < heap.length && heap[c + 1][1] < heap[c][1]) c++;
            if (heap[c][1] >= last[1]) break;
            heap[i] = heap[c];
            i = c;
          }
          heap[i] = last;
        }
        return root;
      };
      const h = (k) =>
        Math.abs(xs[k % nx] - e.t.x) + Math.abs(ys[Math.floor(k / nx)] - e.t.y);
      cost[start * 3 + 2] = 0;
      push(start * 3 + 2, h(start));
      let finish = -1,
        visits = 0;
      while (heap.length && visits++ < N * 6) {
        const [state, estimate] = pop(),
          k = Math.floor(state / 3),
          dir = state % 3;
        if (estimate > cost[state] + h(k) + 0.01) continue;
        if (k === target) {
          finish = state;
          break;
        }
        const options = [
          [1, k + 1, 0],
          [2, k - 1, 0],
          [4, k + nx, 1],
          [8, k - nx, 1],
        ];
        for (const [bit, next, nd] of options) {
          if (
            !(links[k] & bit) ||
            occupied.has(key(k, next)) ||
            turns[next] ||
            (portCells.has(next) && next !== target && next !== start)
          )
            continue;
          if (dir !== 2 && dir !== nd && used[k]) continue;
          const distance =
            nd === 0
              ? Math.abs(xs[k % nx] - xs[next % nx])
              : Math.abs(ys[Math.floor(k / nx)] - ys[Math.floor(next / nx)]);
          const nc =
              cost[state] +
              distance +
              (dir !== 2 && dir !== nd ? 20 : 0) +
              (used[next] ? 35 : 0),
            ns = next * 3 + nd;
          if (nc < cost[ns]) {
            cost[ns] = nc;
            prev[ns] = state;
            push(ns, nc + h(next));
          }
        }
      }
      if (finish < 0) return null;
      const cells = [];
      for (let at = finish; at >= 0; at = prev[at])
        cells.push(Math.floor(at / 3));
      cells.reverse();
      for (let i = 1; i < cells.length; i++) {
        occupied.add(key(cells[i - 1], cells[i]));
        const dir = Math.abs(cells[i] - cells[i - 1]) === 1 ? 1 : 2;
        used[cells[i]] |= dir;
        used[cells[i - 1]] |= dir;
      }
      for (let i = 1; i < cells.length - 1; i++) {
        if (cells[i] - cells[i - 1] !== cells[i + 1] - cells[i])
          turns[cells[i]] = 1;
      }
      const pts = [
        e.start,
        ...cells.map((k) => ({ x: xs[k % nx], y: ys[Math.floor(k / nx)] })),
        e.end,
      ];
      return pts.filter(
        (p, i) =>
          i === 0 ||
          i === pts.length - 1 ||
          !(
            (p.x === pts[i - 1].x && p.x === pts[i + 1].x) ||
            (p.y === pts[i - 1].y && p.y === pts[i + 1].y)
          ),
      );
    }
    const sorted = [...edges].sort(
      (a, b) =>
        Math.abs(a.b - a.a) - Math.abs(b.b - b.a) ||
        (a.type === b.type ? 0 : a.type === "order" ? -1 : 1),
    );
    let omitted = 0;
    for (const e of sorted) {
      e.points = find(e);
      if (!e.points) omitted++;
    }
    return {
      edges: sorted.filter((e) => e.points),
      omitted,
      width: maxX + 160,
      height: maxY + 100,
    };
  }

  // Place labels after routing, beside a clear segment of their own dotted edge.
  function placeGapBadges(layout, routes) {
    const overlap = (a, b) => a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t;
    const rect = (x, y, w, h, p = 0) => ({
      l: x - p,
      r: x + w + p,
      t: y - p,
      b: y + h + p,
    });
    const insideRounded = (r, p) => {
      const radius = 37,
        l = p.x + 7,
        t = p.y + 7,
        right = p.x + p.w - 7,
        bottom = p.y + p.h - 7;
      return [
        [r.l, r.t],
        [r.r, r.t],
        [r.l, r.b],
        [r.r, r.b],
      ].every(([x, y]) => {
        if (x < l || x > right || y < t || y > bottom) return false;
        const cx = Math.max(l + radius, Math.min(right - radius, x)),
          cy = Math.max(t + radius, Math.min(bottom - radius, y));
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2;
      });
    };
    const fixed = [
      ...layout.placed.map((n) => rect(n.x, n.y, W, H, 8)),
      ...layout.obstacles,
    ];
    const segments = routes.edges.flatMap((e) =>
      e.points.slice(1).map((b, i) => ({ a: e.points[i], b, edge: e })),
    );
    const lines = segments.map((s) => ({
      l: Math.min(s.a.x, s.b.x) - 5,
      r: Math.max(s.a.x, s.b.x) + 5,
      t: Math.min(s.a.y, s.b.y) - 5,
      b: Math.max(s.a.y, s.b.y) + 5,
    }));
    const occupied = [],
      badges = [],
      missing = [];
    for (const e of routes.edges.filter((e) => e.type === "gap")) {
      const own = segments.filter((s) => s.edge === e),
        length = own.reduce(
          (sum, s) => sum + Math.abs(s.b.x - s.a.x) + Math.abs(s.b.y - s.a.y),
          0,
        );
      let travelled = 0,
        best = null;
      for (const s of own) {
        const horizontal = s.a.y === s.b.y,
          L = Math.abs(s.b.x - s.a.x) + Math.abs(s.b.y - s.a.y),
          w = 108,
          h = 24,
          along = horizontal ? w : h;
        if (L >= 24) {
          const positions = [L / 2];
          for (let at = 8; at <= L - 8; at += 12) positions.push(at);
          for (const at of positions) {
            const ax = s.a.x + ((s.b.x - s.a.x) * at) / L,
              ay = s.a.y + ((s.b.y - s.a.y) * at) / L;
            for (const gap of [10, 16, 24, 32, 44, 56])
              for (const side of [-1, 1])
                for (const shift of horizontal ? [0, -24, 24, -44, 44] : [0]) {
                  const x = horizontal
                      ? ax - w / 2 + shift
                      : side < 0
                        ? ax - gap - w
                        : ax + gap,
                    y = horizontal
                      ? side < 0
                        ? ay - gap - h
                        : ay + gap
                      : ay - h / 2,
                    r = rect(x, y, w, h, 3);
                  const score =
                    Math.abs(travelled + at - length / 2) +
                    gap * 4 +
                    Math.abs(shift) * 2;
                  if (best && score >= best.score) continue;
                  if (
                    x < 8 ||
                    y < 8 ||
                    fixed.some((o) => overlap(r, o)) ||
                    occupied.some((o) => overlap(r, o)) ||
                    lines.some((o) => overlap(r, o))
                  )
                    continue;
                  // Do not straddle a curved enclosing border.
                  if (
                    layout.parents.some(
                      (p) =>
                        overlap(r, rect(p.x, p.y, p.w, p.h, 7)) &&
                        !insideRounded(r, p),
                    )
                  )
                    continue;
                  best = { ...e, x, y, w, h, anchorX: ax, anchorY: ay, score };
                }
          }
        }
        travelled += L;
      }
      if (best) {
        badges.push(best);
        occupied.push(rect(best.x, best.y, best.w, best.h, 8));
      } else missing.push(e);
    }
    layout.badges = badges;
    layout.unlabelled = missing.length;
    layout.width = Math.max(layout.width, ...badges.map((b) => b.x + b.w + 24));
    layout.height = Math.max(
      layout.height,
      ...badges.map((b) => b.y + b.h + 24),
    );
    return missing;
  }

  const local = nearby({
    current: ordinal.get(String(selectedId)) || 1,
    book: options.book ?? 3,
    dep: options.dependency ?? 2,
    combine: "either",
  });
  const layout = arrange(local.shown, options.view === "hierarchy" ? 1 : 0);
  const ids = new Set(layout.placed.map((n) => n.id));
  const edges = [];
  for (const n of layout.placed)
    if (ids.has(n.id + 1)) edges.push({ a: n.id, b: n.id + 1, type: "order" });
  edges.push(...layout.gaps.map((g) => ({ ...g, type: "gap" })));
  const dependencyEdges = deps
    .filter(([a, b]) => ids.has(a) && ids.has(b))
    .map(([a, b]) => ({ a, b, type: "dependency" }));
  edges.push(
    ...dependencyEdges.slice(0, Math.max(0, EDGE_LIMIT - edges.length)),
  );
  const routes = routeAll(layout.placed, edges, layout.obstacles);
  placeGapBadges(layout, routes);
  return {
    ...layout,
    edges: routes.edges,
    hierarchy,
    candidates: local.candidates,
    omitted:
      routes.omitted +
      dependencyEdges.length -
      edges.filter((e) => e.type === "dependency").length,
    width: Math.max(layout.width, routes.width),
    height: Math.max(layout.height, routes.height),
  };
}
