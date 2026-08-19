from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

try:
    from psycopg2.extras import execute_values
except ImportError:  # Narrow repository test shim; production psycopg2 provides it.
    def execute_values(*args, **kwargs):
        raise RuntimeError("psycopg2.extras.execute_values is unavailable")


GRAPH_CONTRACT_VERSION = 1
GRAPH_SIDECAR_FORMAT = "theumst-knowledge-graph+json"
GRAPH_ROLES = frozenset({"backbone", "support", "assessment", "fragment", "crosslink"})
SUPPORT_ASSESSMENT_TYPES = frozenset({"exercise", "jas"})
MAX_GRAPH_NODES = 500_000
MAX_GRAPH_RELATIONS = 2_000_000
MAX_STABLE_ID_LENGTH = 255
MAX_RELATION_TYPE_LENGTH = 80
_RELATION_TYPE = re.compile(r"^[a-z][a-z0-9_.:-]*$")


@dataclass(frozen=True)
class GraphNode:
    knowledge_id: str
    object_source_key: str
    graph_role: str


@dataclass(frozen=True)
class GraphRelation:
    source_knowledge_id: str
    target_knowledge_id: str
    relation_type: str


@dataclass(frozen=True)
class GraphValidationReceipt:
    receipt_id: str
    sidecar_digest: str
    contract_version: int
    graph_revision: str
    valid: bool
    capability: str
    node_count: int
    relation_count: int
    duplicate_relations: tuple[tuple[str, str, str], ...]
    orphan_references: tuple[str, ...]
    cycle_components: tuple[tuple[str, ...], ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "sidecar_digest": self.sidecar_digest,
            "contract_version": self.contract_version,
            "graph_revision": self.graph_revision,
            "valid": self.valid,
            "capability": self.capability,
            "node_count": self.node_count,
            "relation_count": self.relation_count,
            "duplicate_relations": [list(item) for item in self.duplicate_relations],
            "orphan_references": list(self.orphan_references),
            "cycle_components": [list(component) for component in self.cycle_components],
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ValidatedGraphSidecar:
    nodes: tuple[GraphNode, ...]
    relations: tuple[GraphRelation, ...]
    receipt: GraphValidationReceipt


class GraphSidecarValidationError(ValueError):
    def __init__(self, receipt: GraphValidationReceipt):
        self.receipt = receipt
        super().__init__("; ".join(receipt.errors) or "Invalid knowledge-graph sidecar")


def _canonical_digest(sidecar: Any) -> str:
    encoded = json.dumps(
        sidecar,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any, field: str, errors: list[str], *, maximum: int) -> str:
    if value is not None and not isinstance(value, str):
        errors.append(f"{field} must be a string")
        return ""
    text = str(value or "").strip()
    if not text:
        errors.append(f"{field} is required")
    elif len(text) > maximum:
        errors.append(f"{field} exceeds {maximum} characters")
    elif any(ord(character) < 32 for character in text):
        errors.append(f"{field} contains a control character")
    return text


def _cycle_components(nodes: Iterable[str], relations: Iterable[GraphRelation]) -> tuple[tuple[str, ...], ...]:
    """Return deterministic SCCs without recursion, even for very large books."""
    adjacency = {node: [] for node in nodes}
    reverse = {node: [] for node in adjacency}
    for relation in relations:
        if relation.source_knowledge_id in adjacency and relation.target_knowledge_id in adjacency:
            adjacency[relation.source_knowledge_id].append(relation.target_knowledge_id)
            reverse[relation.target_knowledge_id].append(relation.source_knowledge_id)
    for mapping in (adjacency, reverse):
        for targets in mapping.values():
            targets.sort()

    visited: set[str] = set()
    finish_order: list[str] = []
    for root in sorted(adjacency):
        if root in visited:
            continue
        visited.add(root)
        stack: list[tuple[str, int]] = [(root, 0)]
        while stack:
            node, position = stack[-1]
            if position < len(adjacency[node]):
                target = adjacency[node][position]
                stack[-1] = (node, position + 1)
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0))
            else:
                finish_order.append(node)
                stack.pop()

    assigned: set[str] = set()
    components: list[tuple[str, ...]] = []
    for root in reversed(finish_order):
        if root in assigned:
            continue
        assigned.add(root)
        component: list[str] = []
        stack = [(root, 0)]
        while stack:
            node, position = stack[-1]
            if position == 0:
                component.append(node)
            if position < len(reverse[node]):
                target = reverse[node][position]
                stack[-1] = (node, position + 1)
                if target not in assigned:
                    assigned.add(target)
                    stack.append((target, 0))
            else:
                stack.pop()
        if len(component) > 1:
            components.append(tuple(sorted(component)))
    return tuple(sorted(components))


def validate_graph_sidecar(
    sidecar: Mapping[str, Any],
    objects: Sequence[Mapping[str, Any]],
) -> ValidatedGraphSidecar:
    """Validate an explicit future-ingestion graph without inferring any edge.

    A sidecar is optional at the archive level. When present, it is strict and
    complete: every ingested object must have one stable identity and explicit
    role. The validator never derives relations from type, order, proximity,
    references, sections, or embeddings.
    """
    errors: list[str] = []
    if not isinstance(sidecar, Mapping):
        sidecar = {}
        errors.append("knowledge_graph sidecar must be an object")
    digest = _canonical_digest(sidecar)
    try:
        contract_version = int(sidecar.get("contract_version", sidecar.get("schema_version", 0)))
    except (TypeError, ValueError):
        contract_version = 0
    if contract_version != GRAPH_CONTRACT_VERSION:
        errors.append(f"Unsupported knowledge_graph contract_version {contract_version!r}")
    if "contract_version" in sidecar and "schema_version" in sidecar:
        try:
            schema_version = int(sidecar["schema_version"])
        except (TypeError, ValueError):
            schema_version = 0
        if schema_version != contract_version:
            errors.append("knowledge_graph schema_version and contract_version disagree")
    graph_revision = _text(sidecar.get("graph_revision"), "knowledge_graph.graph_revision", errors, maximum=128)

    object_by_key: dict[str, Mapping[str, Any]] = {}
    duplicate_object_keys: set[str] = set()
    for obj in objects:
        key = str(obj.get("source_key") or "").strip()
        if not key:
            errors.append("Every object needs source_key before graph validation")
            continue
        if key in object_by_key:
            duplicate_object_keys.add(key)
        object_by_key[key] = obj
    for key in sorted(duplicate_object_keys):
        errors.append(f"Duplicate object source_key {key!r}")

    raw_nodes = sidecar.get("nodes", [])
    raw_relations = sidecar.get("relations", [])
    if not isinstance(raw_nodes, list):
        errors.append("knowledge_graph.nodes must be an array")
        raw_nodes = []
    if not isinstance(raw_relations, list):
        errors.append("knowledge_graph.relations must be an array")
        raw_relations = []
    if len(raw_nodes) > MAX_GRAPH_NODES:
        errors.append(f"knowledge_graph.nodes exceeds {MAX_GRAPH_NODES} records")
    if len(raw_relations) > MAX_GRAPH_RELATIONS:
        errors.append(f"knowledge_graph.relations exceeds {MAX_GRAPH_RELATIONS} records")

    nodes: list[GraphNode] = []
    seen_ids: set[str] = set()
    seen_objects: set[str] = set()
    for position, raw_node in enumerate(raw_nodes[: MAX_GRAPH_NODES + 1]):
        if not isinstance(raw_node, Mapping):
            errors.append(f"knowledge_graph.nodes[{position}] must be an object")
            continue
        stable_id = _text(
            raw_node.get("knowledge_id"),
            f"knowledge_graph.nodes[{position}].knowledge_id",
            errors,
            maximum=MAX_STABLE_ID_LENGTH,
        )
        object_key = _text(
            raw_node.get("object_source_key"),
            f"knowledge_graph.nodes[{position}].object_source_key",
            errors,
            maximum=MAX_STABLE_ID_LENGTH,
        )
        role = str(raw_node.get("graph_role") or "").strip()
        if role not in GRAPH_ROLES:
            errors.append(
                f"knowledge_graph.nodes[{position}].graph_role must be one of {', '.join(sorted(GRAPH_ROLES))}"
            )
        if stable_id in seen_ids:
            errors.append(f"Duplicate stable knowledge_id {stable_id!r}")
        if object_key in seen_objects:
            errors.append(f"Duplicate graph object_source_key {object_key!r}")
        obj = object_by_key.get(object_key)
        if object_key and obj is None:
            errors.append(f"Unknown graph object_source_key {object_key!r}")
        if obj is not None:
            working_type = str(obj.get("type") or "").strip().lower()
            if working_type in SUPPORT_ASSESSMENT_TYPES and role not in {"support", "assessment"}:
                errors.append(
                    f"{working_type} object {object_key!r} must use support or assessment graph_role"
                )
        if stable_id:
            seen_ids.add(stable_id)
        if object_key:
            seen_objects.add(object_key)
        if stable_id and object_key and role in GRAPH_ROLES:
            nodes.append(GraphNode(stable_id, object_key, role))

    missing_objects = sorted(set(object_by_key) - seen_objects)
    for object_key in missing_objects:
        errors.append(f"Missing graph node for object_source_key {object_key!r}")

    relations: list[GraphRelation] = []
    relation_keys: set[tuple[str, str, str]] = set()
    duplicates: set[tuple[str, str, str]] = set()
    orphan_references: set[str] = set()
    for position, raw_relation in enumerate(raw_relations[: MAX_GRAPH_RELATIONS + 1]):
        if not isinstance(raw_relation, Mapping):
            errors.append(f"knowledge_graph.relations[{position}] must be an object")
            continue
        source = _text(
            raw_relation.get("source_knowledge_id"),
            f"knowledge_graph.relations[{position}].source_knowledge_id",
            errors,
            maximum=MAX_STABLE_ID_LENGTH,
        )
        target = _text(
            raw_relation.get("target_knowledge_id"),
            f"knowledge_graph.relations[{position}].target_knowledge_id",
            errors,
            maximum=MAX_STABLE_ID_LENGTH,
        )
        relation_type = str(raw_relation.get("relation_type") or "").strip()
        if not relation_type:
            errors.append(f"knowledge_graph.relations[{position}].relation_type is required")
        elif len(relation_type) > MAX_RELATION_TYPE_LENGTH or not _RELATION_TYPE.fullmatch(relation_type):
            errors.append(
                f"knowledge_graph.relations[{position}].relation_type must be a lowercase semantic identifier"
            )
        if source == target and source:
            errors.append(f"Self relation is not allowed for {source!r}")
        if source and source not in seen_ids:
            orphan_references.add(source)
        if target and target not in seen_ids:
            orphan_references.add(target)
        key = (source, target, relation_type)
        if key in relation_keys:
            duplicates.add(key)
            continue
        relation_keys.add(key)
        if source and target and source != target and relation_type and _RELATION_TYPE.fullmatch(relation_type):
            relations.append(GraphRelation(source, target, relation_type))

    for reference in sorted(orphan_references):
        errors.append(f"Relation references unknown knowledge_id {reference!r}")
    cycles = _cycle_components(seen_ids, relations)
    for component in cycles:
        errors.append(f"Directed relation cycle contains: {', '.join(component)}")

    nodes.sort(key=lambda node: node.knowledge_id)
    relations.sort(
        key=lambda relation: (
            relation.source_knowledge_id,
            relation.target_knowledge_id,
            relation.relation_type,
        )
    )
    unique_errors = tuple(sorted(set(errors)))
    capability = "semantic_relations" if relations else "relations_declared_empty"
    valid = not unique_errors
    receipt_seed = json.dumps(
        {
            "sidecar_digest": digest,
            "valid": valid,
            "errors": unique_errors,
            "orphans": sorted(orphan_references),
            "cycles": cycles,
            "duplicates": sorted(duplicates),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    receipt = GraphValidationReceipt(
        receipt_id=hashlib.sha256(receipt_seed.encode("utf-8")).hexdigest(),
        sidecar_digest=digest,
        contract_version=contract_version,
        graph_revision=graph_revision,
        valid=valid,
        capability=capability if valid else "invalid",
        node_count=len(nodes),
        relation_count=len(relations),
        duplicate_relations=tuple(sorted(duplicates)),
        orphan_references=tuple(sorted(orphan_references)),
        cycle_components=cycles,
        errors=unique_errors,
    )
    if not valid:
        raise GraphSidecarValidationError(receipt)
    return ValidatedGraphSidecar(tuple(nodes), tuple(relations), receipt)


def apply_graph_sidecar(
    cur,
    *,
    grimoire_id: int,
    book_source_key: str,
    objects: Mapping[str, Mapping[str, Any]],
    graph: ValidatedGraphSidecar,
    batch_size: int = 1_000,
) -> GraphValidationReceipt:
    """Atomically replace one book's explicit graph after validation."""
    internal_ids = {
        node.knowledge_id: int(objects[node.object_source_key]["knowledge_id"])
        for node in graph.nodes
    }
    cur.execute("DELETE FROM knowledge_graph_node WHERE grimoire_id = %s", (grimoire_id,))
    if graph.nodes:
        execute_values(
            cur,
            """
            INSERT INTO knowledge_graph_node (
                grimoire_id, knowledge_id, stable_knowledge_id, graph_role
            ) VALUES %s
            """,
            [
                (
                    grimoire_id,
                    internal_ids[node.knowledge_id],
                    node.knowledge_id,
                    node.graph_role,
                )
                for node in graph.nodes
            ],
            page_size=batch_size,
        )
    if graph.relations:
        execute_values(
            cur,
            """
            INSERT INTO knowledge_graph_edge (
                grimoire_id, source_knowledge_id, target_knowledge_id, relation_type
            ) VALUES %s
            """,
            [
                (
                    grimoire_id,
                    internal_ids[relation.source_knowledge_id],
                    internal_ids[relation.target_knowledge_id],
                    relation.relation_type,
                )
                for relation in graph.relations
            ],
            page_size=batch_size,
        )
    receipt = graph.receipt
    cur.execute(
        """
        INSERT INTO knowledge_graph_receipt (
            receipt_id, grimoire_id, book_source_key, contract_version,
            graph_revision, sidecar_digest, capability, node_count,
            relation_count, diagnostics
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (grimoire_id, receipt_id) DO UPDATE SET
            book_source_key = EXCLUDED.book_source_key,
            graph_revision = EXCLUDED.graph_revision,
            capability = EXCLUDED.capability,
            node_count = EXCLUDED.node_count,
            relation_count = EXCLUDED.relation_count,
            diagnostics = EXCLUDED.diagnostics
        """,
        (
            receipt.receipt_id,
            grimoire_id,
            book_source_key,
            receipt.contract_version,
            receipt.graph_revision,
            receipt.sidecar_digest,
            receipt.capability,
            receipt.node_count,
            receipt.relation_count,
            json.dumps(receipt.as_dict(), separators=(",", ":")),
        ),
    )
    cur.execute(
        """
        UPDATE grimoire
        SET graph_contract_version = %s,
            graph_revision = %s,
            graph_capability = %s,
            graph_receipt_id = %s
        WHERE grimoire_id = %s
        """,
        (
            receipt.contract_version,
            receipt.graph_revision,
            receipt.capability,
            receipt.receipt_id,
            grimoire_id,
        ),
    )
    return receipt


def build_contents_tree(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a hierarchy only from stored section parent metadata."""
    nodes: dict[int, dict[str, Any]] = {}
    parent_by_id: dict[int, int | None] = {}
    for row in rows:
        section_id = int(row["section_id"])
        parent = row.get("parent_section")
        parent_by_id[section_id] = int(parent) if parent is not None else None
        nodes[section_id] = {
            "section_id": section_id,
            "section_source_key": row.get("section_source_key"),
            "section_number": row.get("section_number"),
            "section_name": row.get("section_name"),
            "section_head": row.get("section_head"),
            "section_tail": row.get("section_tail"),
            "children": [],
        }
    cycle_sections: set[int] = set()
    finished: set[int] = set()
    for start in sorted(nodes):
        chain: list[int] = []
        positions: dict[int, int] = {}
        current: int | None = start
        while current is not None and current in nodes and current not in finished:
            if current in positions:
                cycle_sections.update(chain[positions[current] :])
                break
            positions[current] = len(chain)
            chain.append(current)
            current = parent_by_id[current]
        finished.update(chain)
    orphans: list[int] = []
    roots: list[dict[str, Any]] = []
    for section_id in sorted(nodes, key=lambda item: (str(nodes[item].get("section_number") or ""), item)):
        parent = parent_by_id[section_id]
        if parent is None:
            roots.append(nodes[section_id])
        elif section_id in cycle_sections and parent in cycle_sections:
            nodes[section_id]["hierarchy_state"] = "cycle"
            roots.append(nodes[section_id])
        elif parent in nodes:
            nodes[parent]["children"].append(nodes[section_id])
        else:
            orphans.append(section_id)
    return {
        "sections": roots,
        "orphan_section_ids": sorted(orphans),
        "cycle_section_ids": sorted(cycle_sections),
        "section_count": len(nodes),
    }


def fetch_contents(cur, *, grimoire_id: int, language_id: int = 1) -> dict[str, Any]:
    """Fetch immutable section contents in one indexed, book-scoped query."""
    cur.execute(
        """
        SELECT s.section_id, s.parent_section, s.source_key AS section_source_key,
               s.section_number, ls.section_name, ls.section_head, ls.section_tail
        FROM section s
        LEFT JOIN language_section ls
          ON ls.section_id = s.section_id AND ls.language_id = %s
        WHERE s.grimoire_id = %s
        ORDER BY s.section_id
        """,
        (language_id, grimoire_id),
    )
    return build_contents_tree([dict(row) for row in cur.fetchall()])


FOCUSED_GRAPH_MAX_NODES = 150
FOCUSED_GRAPH_MAX_DEPTH = 2
FOCUSED_GRAPH_EDGE_MULTIPLIER = 4
FOCUSED_GRAPH_CANDIDATE_MULTIPLIER = 4


def _focus_row(cur, *, grimoire_id: int, focus: str | int, language_id: int) -> dict[str, Any] | None:
    focus_text = str(focus)
    if isinstance(focus, int) or focus_text.isdigit():
        identity_clause = "n.knowledge_id = %s"
        identity_value: Any = int(focus_text)
    else:
        identity_clause = "n.stable_knowledge_id = %s"
        identity_value = focus_text
    cur.execute(
        f"""
        SELECT n.knowledge_id, n.stable_knowledge_id, n.graph_role,
               COALESCE(lk.label, lk.statement, n.stable_knowledge_id) AS label,
               k.type, g.graph_revision, g.graph_capability
        FROM knowledge_graph_node n
        JOIN knowledge k ON k.knowledge_id = n.knowledge_id AND k.is_active
        JOIN grimoire g ON g.grimoire_id = n.grimoire_id
        LEFT JOIN language_knowledge lk
          ON lk.knowledge_id = n.knowledge_id AND lk.language_id = %s
        WHERE n.grimoire_id = %s
          AND g.graph_capability <> 'unavailable'
          AND {identity_clause}
        LIMIT 1
        """,
        (language_id, grimoire_id, identity_value),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _relationless_focus_row(
    cur,
    *,
    grimoire_id: int,
    focus: str | int,
    language_id: int,
) -> dict[str, Any] | None:
    focus_text = str(focus)
    if not (isinstance(focus, int) or focus_text.isdigit()):
        return None
    cur.execute(
        """
        SELECT k.knowledge_id, NULL::text AS stable_knowledge_id,
               'fragment'::text AS graph_role,
               COALESCE(lk.label, lk.statement, k.source_key, k.knowledge_id::text) AS label,
               k.type, g.graph_revision, g.graph_capability
        FROM knowledge k
        JOIN section s ON s.section_id = k.section_id
        JOIN grimoire g ON g.grimoire_id = s.grimoire_id
        LEFT JOIN language_knowledge lk
          ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %s
        WHERE s.grimoire_id = %s AND k.knowledge_id = %s AND k.is_active
        LIMIT 1
        """,
        (language_id, grimoire_id, int(focus_text)),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _walk_graph(
    cur,
    *,
    grimoire_id: int,
    frontier: list[int],
    selected: list[int],
    selected_set: set[int],
    depth: int,
    limit: int,
    include_roles: Sequence[str],
    direction: str,
) -> None:
    if direction == "ancestor":
        candidate_column = "source_knowledge_id"
        frontier_column = "target_knowledge_id"
    elif direction == "descendant":
        candidate_column = "target_knowledge_id"
        frontier_column = "source_knowledge_id"
    else:
        raise ValueError("direction must be ancestor or descendant")
    for _ in range(depth):
        remaining = limit - len(selected)
        if remaining <= 0 or not frontier:
            return
        candidate_limit = min(
            FOCUSED_GRAPH_MAX_NODES * FOCUSED_GRAPH_CANDIDATE_MULTIPLIER,
            max(remaining, remaining * FOCUSED_GRAPH_CANDIDATE_MULTIPLIER),
        )
        cur.execute(
            f"""
            SELECT edge.{candidate_column} AS candidate_knowledge_id
            FROM knowledge_graph_edge edge
            JOIN knowledge_graph_node candidate
              ON candidate.grimoire_id = edge.grimoire_id
             AND candidate.knowledge_id = edge.{candidate_column}
            WHERE edge.grimoire_id = %s
              AND edge.{frontier_column} = ANY(%s::int[])
              AND (candidate.graph_role = 'backbone' OR candidate.graph_role = ANY(%s::text[]))
            ORDER BY edge.{frontier_column}, edge.{candidate_column}, edge.relation_type
            LIMIT %s
            """,
            (grimoire_id, frontier, list(include_roles), candidate_limit),
        )
        next_frontier: list[int] = []
        for row in cur.fetchall():
            candidate_id = int(row["candidate_knowledge_id"])
            if candidate_id in selected_set:
                continue
            selected_set.add(candidate_id)
            selected.append(candidate_id)
            next_frontier.append(candidate_id)
            if len(selected) >= limit:
                break
        frontier = next_frontier


def fetch_authored_relation_graph(
    cur,
    *,
    grimoire_id: int,
    focus: str | int,
    ancestor_depth: int = 2,
    descendant_depth: int = 2,
    include_roles: Sequence[str] = ("support", "assessment"),
    limit: int = 150,
    language_id: int = 1,
) -> dict[str, Any]:
    """Return a hard-bounded semantic slice; never substitute similarity edges.

    Traversal is performed as a small breadth-first sequence so every database
    read has an explicit transfer cap. A highly connected book therefore cannot
    make a focus request materialize the full graph as an intermediate result.
    """
    if not 1 <= limit <= FOCUSED_GRAPH_MAX_NODES:
        raise ValueError(f"limit must be between 1 and {FOCUSED_GRAPH_MAX_NODES}")
    if not 0 <= ancestor_depth <= FOCUSED_GRAPH_MAX_DEPTH or not 0 <= descendant_depth <= FOCUSED_GRAPH_MAX_DEPTH:
        raise ValueError(f"graph depths must be between 0 and {FOCUSED_GRAPH_MAX_DEPTH}")
    requested_roles = tuple(sorted(set(include_roles)))
    if any(role not in GRAPH_ROLES - {"backbone"} for role in requested_roles):
        raise ValueError("include_roles contains an unsupported graph role")

    focus_row = _focus_row(
        cur,
        grimoire_id=grimoire_id,
        focus=focus,
        language_id=language_id,
    )
    if focus_row is None:
        focus_row = _relationless_focus_row(
            cur,
            grimoire_id=grimoire_id,
            focus=focus,
            language_id=language_id,
        )
        if focus_row is None:
            raise LookupError("The focus knowledge item is not available in this book")
        return {
            "nodes": [{
                "knowledge_id": int(focus_row["knowledge_id"]),
                "label": focus_row["label"],
                "type": focus_row["type"],
                "graph_role": "fragment",
                "collapsed_ancestor_count": 0,
                "collapsed_descendant_count": 0,
                "stable_knowledge_id": None,
            }],
            "edges": [],
            "graph_revision": focus_row.get("graph_revision") or "",
            "focus_knowledge_id": int(focus_row["knowledge_id"]),
            "graph_capability": focus_row.get("graph_capability") or "unavailable",
            "edges_truncated": False,
        }

    focus_id = int(focus_row["knowledge_id"])
    selected = [focus_id]
    selected_set = {focus_id}
    _walk_graph(
        cur,
        grimoire_id=grimoire_id,
        frontier=[focus_id],
        selected=selected,
        selected_set=selected_set,
        depth=ancestor_depth,
        limit=limit,
        include_roles=requested_roles,
        direction="ancestor",
    )
    _walk_graph(
        cur,
        grimoire_id=grimoire_id,
        frontier=[focus_id],
        selected=selected,
        selected_set=selected_set,
        depth=descendant_depth,
        limit=limit,
        include_roles=requested_roles,
        direction="descendant",
    )

    cur.execute(
        """
        SELECT n.knowledge_id, n.stable_knowledge_id, n.graph_role,
               COALESCE(lk.label, lk.statement, n.stable_knowledge_id) AS label,
               k.type,
               (SELECT count(*)
                FROM knowledge_graph_edge edge
                WHERE edge.grimoire_id = n.grimoire_id
                  AND edge.target_knowledge_id = n.knowledge_id
                  AND NOT (edge.source_knowledge_id = ANY(%s::int[])))::int
                    AS collapsed_ancestor_count,
               (SELECT count(*)
                FROM knowledge_graph_edge edge
                WHERE edge.grimoire_id = n.grimoire_id
                  AND edge.source_knowledge_id = n.knowledge_id
                  AND NOT (edge.target_knowledge_id = ANY(%s::int[])))::int
                    AS collapsed_descendant_count
        FROM knowledge_graph_node n
        JOIN knowledge k ON k.knowledge_id = n.knowledge_id AND k.is_active
        LEFT JOIN language_knowledge lk
          ON lk.knowledge_id = n.knowledge_id AND lk.language_id = %s
        WHERE n.grimoire_id = %s AND n.knowledge_id = ANY(%s::int[])
        ORDER BY array_position(%s::int[], n.knowledge_id)
        LIMIT %s
        """,
        (selected, selected, language_id, grimoire_id, selected, selected, limit),
    )
    node_rows = [dict(row) for row in cur.fetchall()]
    nodes = [
        {
            "knowledge_id": int(row["knowledge_id"]),
            "label": row["label"],
            "type": row["type"],
            "graph_role": row["graph_role"],
            "collapsed_ancestor_count": int(row["collapsed_ancestor_count"]),
            "collapsed_descendant_count": int(row["collapsed_descendant_count"]),
            "stable_knowledge_id": row["stable_knowledge_id"],
        }
        for row in node_rows
    ]

    edge_limit = limit * FOCUSED_GRAPH_EDGE_MULTIPLIER
    cur.execute(
        """
        SELECT edge.source_knowledge_id, edge.target_knowledge_id, edge.relation_type,
               source.stable_knowledge_id AS source_stable_knowledge_id,
               target.stable_knowledge_id AS target_stable_knowledge_id
        FROM knowledge_graph_edge edge
        JOIN knowledge_graph_node source
          ON source.grimoire_id = edge.grimoire_id
         AND source.knowledge_id = edge.source_knowledge_id
        JOIN knowledge_graph_node target
          ON target.grimoire_id = edge.grimoire_id
         AND target.knowledge_id = edge.target_knowledge_id
        WHERE edge.grimoire_id = %s
          AND edge.source_knowledge_id = ANY(%s::int[])
          AND edge.target_knowledge_id = ANY(%s::int[])
        ORDER BY edge.source_knowledge_id, edge.target_knowledge_id, edge.relation_type
        LIMIT %s
        """,
        (grimoire_id, selected, selected, edge_limit + 1),
    )
    edge_rows = [dict(row) for row in cur.fetchall()]
    edges_truncated = len(edge_rows) > edge_limit
    edges = [
        {
            "source_knowledge_id": int(row["source_knowledge_id"]),
            "target_knowledge_id": int(row["target_knowledge_id"]),
            "relation_type": row["relation_type"],
            "source_stable_knowledge_id": row["source_stable_knowledge_id"],
            "target_stable_knowledge_id": row["target_stable_knowledge_id"],
        }
        for row in edge_rows[:edge_limit]
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "graph_revision": focus_row.get("graph_revision") or "",
        "focus_knowledge_id": focus_id,
        "graph_capability": focus_row.get("graph_capability") or "unavailable",
        "edges_truncated": edges_truncated,
    }


# Current-release graph projection. Authored semantic relations above remain a
# separate future capability; they are never blended with this deterministic
# book-order view or with embedding similarity.
BOOK_ORDER_PROJECTION_VERSION = "book_order_v1"
BOOK_ORDER_RELATION_TYPE = "book_order_v1"
BOOK_ORDER_SOURCE = "knowledge.source_metadata.order"
BOOK_ORDER_BACKBONE_TYPES = frozenset({
    "definition",
    "notation",
    "theorem",
    "lemma",
    "proposition",
    "corollary",
    "just a statement",
})


class BookOrderProjectionError(ValueError):
    """Raised when canonical book order cannot support an honest projection."""


def _canonical_book_position(value: Any) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise BookOrderProjectionError(
            "Canonical book position must be a non-empty array of non-negative integers"
        )
    position: list[int] = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, int) or component < 0:
            raise BookOrderProjectionError(
                "Canonical book position must be a non-empty array of non-negative integers"
            )
        position.append(component)
    return tuple(position)


def _book_order_graph_role(item: Mapping[str, Any]) -> str:
    working_type = str(item.get("type") or "").strip().lower()
    # These two support/assessment types are never allowed to take the spine,
    # even if an older type map or an explicit sidecar role says otherwise.
    if working_type == "exercise":
        return "assessment"
    if working_type == "jas":
        return "support"
    explicit_role = item.get("graph_role")
    if explicit_role is not None:
        role = str(explicit_role).strip().lower()
        if role not in GRAPH_ROLES:
            raise BookOrderProjectionError("Graph role is not valid for book_order_v1")
        return role
    return "backbone" if working_type in BOOK_ORDER_BACKBONE_TYPES else "support"


def build_book_order_v1_projection(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build Christopher's deterministic spine-and-fan projection in memory.

    This pure helper is used for invariant tests and small offline preparation.
    The request path below performs the same projection in PostgreSQL and
    transfers only the bounded focus slice to the application.
    """
    prepared: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for original in items:
        try:
            knowledge_id = int(original["knowledge_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BookOrderProjectionError("Every projected item needs a stable numeric knowledge_id") from exc
        if isinstance(original.get("knowledge_id"), bool) or knowledge_id <= 0 or knowledge_id in seen_ids:
            raise BookOrderProjectionError("Projected knowledge_id values must be unique positive integers")
        seen_ids.add(knowledge_id)
        position = _canonical_book_position(original.get("canonical_book_position"))
        prepared.append({
            **dict(original),
            "knowledge_id": knowledge_id,
            "canonical_book_position": list(position),
            "_position": position,
            "graph_role": _book_order_graph_role(original),
        })

    prepared.sort(key=lambda item: (item["_position"], item["knowledge_id"]))
    if not prepared:
        raise BookOrderProjectionError("The book has no ordered knowledge items")

    first = prepared[0]
    anchor_id = int(first["knowledge_id"])
    leading_non_main_anchor_id = (
        anchor_id if first["graph_role"] != "backbone" else None
    )
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[int, int]] = set()

    for rank, item in enumerate(prepared, start=1):
        knowledge_id = int(item["knowledge_id"])
        item_anchor_id = anchor_id
        if rank > 1:
            edge = (anchor_id, knowledge_id)
            if edge not in seen_edges:
                seen_edges.add(edge)
                edges.append({
                    "source_knowledge_id": anchor_id,
                    "target_knowledge_id": knowledge_id,
                    "relation_type": BOOK_ORDER_RELATION_TYPE,
                    "projection_version": BOOK_ORDER_PROJECTION_VERSION,
                    "authored_relation": False,
                })
        nodes.append({
            "knowledge_id": knowledge_id,
            "label": item.get("label") or item.get("source_key") or str(knowledge_id),
            "type": item.get("type"),
            "graph_role": item["graph_role"],
            "stable_knowledge_id": item.get("stable_knowledge_id"),
            "canonical_book_position": item["canonical_book_position"],
            "book_order_rank": rank,
            "book_order_anchor_knowledge_id": item_anchor_id,
            "is_provisional_anchor": bool(
                rank == 1 and item["graph_role"] != "backbone"
            ),
        })
        if item["graph_role"] == "backbone":
            anchor_id = knowledge_id

    revision_material = [
        [
            node["canonical_book_position"],
            node["knowledge_id"],
            node["graph_role"],
        ]
        for node in nodes
    ]
    revision = hashlib.sha256(
        json.dumps(revision_material, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "nodes": nodes,
        "edges": edges,
        "graph_revision": f"{BOOK_ORDER_PROJECTION_VERSION}:{revision}",
        "graph_capability": "book_order_projection",
        "projection_metadata": {
            "version": BOOK_ORDER_PROJECTION_VERSION,
            "relation_type": BOOK_ORDER_RELATION_TYPE,
            "source": BOOK_ORDER_SOURCE,
            "authored_dependencies": False,
            "leading_non_main_anchor_knowledge_id": leading_non_main_anchor_id,
        },
    }


def slice_book_order_v1_projection(
    projection: Mapping[str, Any],
    *,
    focus: int,
    ancestor_depth: int = 2,
    descendant_depth: int = 2,
    include_roles: Sequence[str] = ("support", "assessment"),
    limit: int = 150,
) -> dict[str, Any]:
    """Return a deterministic bounded slice of a prepared book_order_v1 DAG."""
    if not 1 <= limit <= FOCUSED_GRAPH_MAX_NODES:
        raise ValueError(f"limit must be between 1 and {FOCUSED_GRAPH_MAX_NODES}")
    if not 0 <= ancestor_depth <= FOCUSED_GRAPH_MAX_DEPTH or not 0 <= descendant_depth <= FOCUSED_GRAPH_MAX_DEPTH:
        raise ValueError(f"graph depths must be between 0 and {FOCUSED_GRAPH_MAX_DEPTH}")
    requested_roles = tuple(sorted(set(include_roles)))
    if any(role not in GRAPH_ROLES - {"backbone"} for role in requested_roles):
        raise ValueError("include_roles contains an unsupported graph role")

    nodes_by_id = {
        int(node["knowledge_id"]): dict(node)
        for node in projection.get("nodes") or []
    }
    focus_id = int(focus)
    if focus_id not in nodes_by_id:
        raise LookupError("The focus knowledge item is not available in this book")
    outgoing: dict[int, list[int]] = {}
    incoming: dict[int, list[int]] = {}
    for edge in projection.get("edges") or []:
        source = int(edge["source_knowledge_id"])
        target = int(edge["target_knowledge_id"])
        outgoing.setdefault(source, []).append(target)
        incoming.setdefault(target, []).append(source)
    order_key = lambda item: (
        int(nodes_by_id[item]["book_order_rank"]),
        item,
    )
    for values in (*outgoing.values(), *incoming.values()):
        values.sort(key=order_key)

    selected: list[int] = [focus_id]
    selected_set = {focus_id}

    def add_walk(*, adjacency: Mapping[int, list[int]], depth: int, descendants: bool) -> None:
        frontier = [focus_id]
        for _ in range(depth):
            candidates: list[int] = []
            for current in frontier:
                for candidate in adjacency.get(current, []):
                    if candidate in selected_set:
                        continue
                    role = nodes_by_id[candidate]["graph_role"]
                    if descendants and role != "backbone" and role not in requested_roles:
                        continue
                    candidates.append(candidate)
            frontier = []
            for candidate in sorted(set(candidates), key=order_key):
                if len(selected) >= limit:
                    return
                selected_set.add(candidate)
                selected.append(candidate)
                frontier.append(candidate)

    add_walk(adjacency=incoming, depth=ancestor_depth, descendants=False)
    add_walk(adjacency=outgoing, depth=descendant_depth, descendants=True)

    sliced_nodes = []
    for knowledge_id in sorted(selected, key=order_key):
        node = dict(nodes_by_id[knowledge_id])
        node["collapsed_ancestor_count"] = sum(
            1 for source in incoming.get(knowledge_id, []) if source not in selected_set
        )
        node["collapsed_descendant_count"] = sum(
            1 for target in outgoing.get(knowledge_id, []) if target not in selected_set
        )
        sliced_nodes.append(node)
    sliced_edges = [
        dict(edge)
        for edge in projection.get("edges") or []
        if int(edge["source_knowledge_id"]) in selected_set
        and int(edge["target_knowledge_id"]) in selected_set
    ]
    sliced_edges.sort(key=lambda edge: (
        order_key(int(edge["source_knowledge_id"])),
        order_key(int(edge["target_knowledge_id"])),
    ))
    return {
        "nodes": sliced_nodes,
        "edges": sliced_edges,
        "graph_revision": projection.get("graph_revision") or "",
        "focus_knowledge_id": focus_id,
        "graph_capability": "book_order_projection",
        "projection_metadata": dict(projection.get("projection_metadata") or {}),
        "edges_truncated": False,
    }


def fetch_focused_graph(
    cur,
    *,
    grimoire_id: int,
    focus: str | int,
    ancestor_depth: int = 2,
    descendant_depth: int = 2,
    include_roles: Sequence[str] = ("support", "assessment"),
    limit: int = 150,
    language_id: int = 1,
) -> dict[str, Any]:
    """Return a bounded `book_order_v1` slice without transferring the full book.

    PostgreSQL computes the deterministic projection and recursive focus walk;
    only one aggregate result containing at most ``limit`` nodes crosses the
    database/application boundary.
    """
    if not 1 <= limit <= FOCUSED_GRAPH_MAX_NODES:
        raise ValueError(f"limit must be between 1 and {FOCUSED_GRAPH_MAX_NODES}")
    if not 0 <= ancestor_depth <= FOCUSED_GRAPH_MAX_DEPTH or not 0 <= descendant_depth <= FOCUSED_GRAPH_MAX_DEPTH:
        raise ValueError(f"graph depths must be between 0 and {FOCUSED_GRAPH_MAX_DEPTH}")
    requested_roles = tuple(sorted(set(include_roles)))
    if any(role not in GRAPH_ROLES - {"backbone"} for role in requested_roles):
        raise ValueError("include_roles contains an unsupported graph role")
    focus_text = str(focus)
    if not (isinstance(focus, int) or focus_text.isdigit()):
        raise LookupError("The focus knowledge item is not available in this book")
    focus_id = int(focus_text)

    # This query deliberately keeps book-wide ordering work inside PostgreSQL.
    # The result crossing the driver boundary is one row with a maximum of 150
    # nodes. Canonical positions must be non-empty integer arrays; a malformed
    # position makes the whole projection unavailable instead of being guessed.
    cur.execute(
        """
        WITH RECURSIVE raw AS (
            SELECT k.knowledge_id, k.type, k.source_key,
                   k.source_metadata->'order' AS canonical_position,
                   COALESCE(lk.label, lk.statement, k.source_key, k.knowledge_id::text) AS label,
                   explicit.stable_knowledge_id,
                   CASE
                       WHEN lower(COALESCE(k.type, '')) = 'exercise' THEN 'assessment'
                       WHEN lower(COALESCE(k.type, '')) = 'jas' THEN 'support'
                       WHEN explicit.graph_role IS NOT NULL THEN explicit.graph_role
                       WHEN lower(COALESCE(k.type, '')) = ANY(%s::text[]) THEN 'backbone'
                       ELSE 'support'
                   END AS graph_role
            FROM knowledge k
            JOIN section s ON s.section_id = k.section_id
            LEFT JOIN language_knowledge lk
              ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %s
            LEFT JOIN knowledge_graph_node explicit
              ON explicit.grimoire_id = s.grimoire_id
             AND explicit.knowledge_id = k.knowledge_id
            WHERE s.grimoire_id = %s AND k.is_active
        ), validated AS (
            SELECT raw.*,
                   CASE
                       WHEN canonical_position IS NULL THEN false
                       WHEN jsonb_typeof(canonical_position) <> 'array' THEN false
                       WHEN jsonb_array_length(canonical_position) = 0 THEN false
                       ELSE NOT EXISTS (
                           SELECT 1
                           FROM jsonb_array_elements(canonical_position) component(value)
                           WHERE CASE
                               WHEN jsonb_typeof(component.value) = 'number' THEN
                                   (component.value::text)::numeric < 0
                                   OR (component.value::text)::numeric
                                      <> trunc((component.value::text)::numeric)
                               ELSE true
                           END
                       )
                   END AS position_valid
            FROM raw
        ), validation AS (
            SELECT count(*)::int AS total_count,
                   count(*) FILTER (WHERE NOT position_valid)::int AS invalid_count
            FROM validated
        ), ordered AS (
            SELECT validated.*,
                   row_number() OVER (
                       ORDER BY canonical_position, knowledge_id
                   )::int AS position_rank
            FROM validated
            WHERE position_valid
        ), anchor_basis AS (
            SELECT ordered.*,
                   first_value(knowledge_id) OVER (
                       ORDER BY position_rank
                       ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                   ) AS first_knowledge_id,
                   max(position_rank) FILTER (WHERE graph_role = 'backbone') OVER (
                       ORDER BY position_rank
                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                   ) AS preceding_backbone_rank
            FROM ordered
        ), projected_nodes AS (
            SELECT basis.*,
                   COALESCE(backbone.knowledge_id, basis.first_knowledge_id) AS anchor_knowledge_id
            FROM anchor_basis basis
            LEFT JOIN ordered backbone
              ON backbone.position_rank = basis.preceding_backbone_rank
        ), projected_edges AS (
            SELECT anchor_knowledge_id AS source_knowledge_id,
                   knowledge_id AS target_knowledge_id,
                   %s::text AS relation_type
            FROM projected_nodes
            WHERE position_rank > 1 AND anchor_knowledge_id <> knowledge_id
        ), ancestor_walk(knowledge_id, depth) AS (
            SELECT knowledge_id, 0
            FROM projected_nodes WHERE knowledge_id = %s
            UNION ALL
            SELECT edge.source_knowledge_id, walk.depth + 1
            FROM ancestor_walk walk
            JOIN projected_edges edge
              ON edge.target_knowledge_id = walk.knowledge_id
            WHERE walk.depth < %s
        ), descendant_walk(knowledge_id, depth) AS (
            SELECT knowledge_id, 0
            FROM projected_nodes WHERE knowledge_id = %s
            UNION ALL
            SELECT edge.target_knowledge_id, walk.depth + 1
            FROM descendant_walk walk
            JOIN projected_edges edge
              ON edge.source_knowledge_id = walk.knowledge_id
            JOIN projected_nodes candidate
              ON candidate.knowledge_id = edge.target_knowledge_id
            WHERE walk.depth < %s
              AND (
                  candidate.graph_role = 'backbone'
                  OR candidate.graph_role = ANY(%s::text[])
              )
        ), walk_candidates AS (
            SELECT knowledge_id, 0 AS direction_priority, 0 AS depth
            FROM projected_nodes WHERE knowledge_id = %s
            UNION ALL
            SELECT knowledge_id, 1, depth FROM ancestor_walk WHERE depth > 0
            UNION ALL
            SELECT knowledge_id, 2, depth FROM descendant_walk WHERE depth > 0
        ), ranked_candidates AS (
            SELECT knowledge_id, min(direction_priority) AS direction_priority,
                   min(depth) AS depth
            FROM walk_candidates
            GROUP BY knowledge_id
        ), selected AS (
            SELECT candidate.knowledge_id
            FROM ranked_candidates candidate
            JOIN projected_nodes node ON node.knowledge_id = candidate.knowledge_id
            ORDER BY candidate.direction_priority, candidate.depth,
                     node.position_rank, node.knowledge_id
            LIMIT %s
        ), revision AS (
            SELECT md5(COALESCE(string_agg(
                       canonical_position::text || ':' || knowledge_id::text || ':' || graph_role,
                       '|' ORDER BY position_rank
                   ), '')) AS digest
            FROM projected_nodes
        )
        SELECT validation.total_count, validation.invalid_count,
               EXISTS (
                   SELECT 1 FROM projected_nodes WHERE knowledge_id = %s
               ) AS focus_exists,
               revision.digest AS projection_digest,
               (
                   SELECT first.knowledge_id
                   FROM projected_nodes first
                   WHERE first.position_rank = 1 AND first.graph_role <> 'backbone'
               ) AS leading_non_main_anchor_knowledge_id,
               COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                       'knowledge_id', node.knowledge_id,
                       'label', node.label,
                       'type', node.type,
                       'graph_role', node.graph_role,
                       'stable_knowledge_id', node.stable_knowledge_id,
                       'canonical_book_position', node.canonical_position,
                       'book_order_rank', node.position_rank,
                       'book_order_anchor_knowledge_id', node.anchor_knowledge_id,
                       'is_provisional_anchor',
                           node.position_rank = 1 AND node.graph_role <> 'backbone',
                       'collapsed_ancestor_count', (
                           SELECT count(*)::int FROM projected_edges edge
                           WHERE edge.target_knowledge_id = node.knowledge_id
                             AND NOT EXISTS (
                                 SELECT 1 FROM selected chosen
                                 WHERE chosen.knowledge_id = edge.source_knowledge_id
                             )
                       ),
                       'collapsed_descendant_count', (
                           SELECT count(*)::int FROM projected_edges edge
                           WHERE edge.source_knowledge_id = node.knowledge_id
                             AND NOT EXISTS (
                                 SELECT 1 FROM selected chosen
                                 WHERE chosen.knowledge_id = edge.target_knowledge_id
                             )
                       )
                   ) ORDER BY node.position_rank, node.knowledge_id)
                   FROM projected_nodes node
                   JOIN selected chosen ON chosen.knowledge_id = node.knowledge_id
               ), '[]'::jsonb) AS nodes,
               COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                       'source_knowledge_id', edge.source_knowledge_id,
                       'target_knowledge_id', edge.target_knowledge_id,
                       'relation_type', edge.relation_type,
                       'source_stable_knowledge_id', source.stable_knowledge_id,
                       'target_stable_knowledge_id', target.stable_knowledge_id,
                       'projection_version', %s::text,
                       'authored_relation', false
                   ) ORDER BY source.position_rank, target.position_rank)
                   FROM projected_edges edge
                   JOIN selected source_selected
                     ON source_selected.knowledge_id = edge.source_knowledge_id
                   JOIN selected target_selected
                     ON target_selected.knowledge_id = edge.target_knowledge_id
                   JOIN projected_nodes source
                     ON source.knowledge_id = edge.source_knowledge_id
                   JOIN projected_nodes target
                     ON target.knowledge_id = edge.target_knowledge_id
               ), '[]'::jsonb) AS edges
        FROM validation CROSS JOIN revision
        """,
        (
            list(sorted(BOOK_ORDER_BACKBONE_TYPES)),
            language_id,
            grimoire_id,
            BOOK_ORDER_RELATION_TYPE,
            focus_id,
            ancestor_depth,
            focus_id,
            descendant_depth,
            list(requested_roles),
            focus_id,
            limit,
            focus_id,
            BOOK_ORDER_PROJECTION_VERSION,
        ),
    )
    row = cur.fetchone()
    if not row or int(row.get("total_count") or 0) == 0:
        raise LookupError("The focus knowledge item is not available in this book")
    if int(row.get("invalid_count") or 0):
        raise BookOrderProjectionError(
            "This book does not have an unambiguous canonical order for its learning map"
        )
    if not row.get("focus_exists"):
        raise LookupError("The focus knowledge item is not available in this book")
    nodes = [dict(node) for node in (row.get("nodes") or [])]
    edges = [dict(edge) for edge in (row.get("edges") or [])]
    return {
        "nodes": nodes,
        "edges": edges,
        "graph_revision": (
            f"{BOOK_ORDER_PROJECTION_VERSION}:{row.get('projection_digest') or ''}"
        ),
        "focus_knowledge_id": focus_id,
        "graph_capability": "book_order_projection",
        "projection_metadata": {
            "version": BOOK_ORDER_PROJECTION_VERSION,
            "relation_type": BOOK_ORDER_RELATION_TYPE,
            "source": BOOK_ORDER_SOURCE,
            "authored_dependencies": False,
            "leading_non_main_anchor_knowledge_id": row.get(
                "leading_non_main_anchor_knowledge_id"
            ),
        },
        "edges_truncated": False,
    }
