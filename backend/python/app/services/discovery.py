"""Stored-projection discovery. PostgreSQL determines readable candidates."""
from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException

from ..database import transaction
from .game_search import book_scope, scope_filter
from .qdrant import qdrant_service


def combined_score(statement: float, combined: float | None, source_workings: bool, target_workings: bool) -> float:
    """Map cosine to [0,1] before penalizing a mismatch in available content."""
    if not math.isfinite(statement) or not -1.000001 <= statement <= 1.000001:
        raise ValueError('Invalid cosine statement score')
    statement = (max(-1.0, min(1.0, statement)) + 1) / 2
    if source_workings and target_workings:
        if combined is None or not math.isfinite(combined) or not -1.000001 <= combined <= 1.000001:
            raise ValueError('Missing or invalid combined projection score')
        return (statement + (max(-1.0, min(1.0, combined)) + 1) / 2) / 2
    return statement * .8 if source_workings != target_workings else statement


_PROJECTIONS_SQL = """
    SELECT e.embedding_id::text, e.embedding_model_id, sp.projection_type,
           sp.language_id, sp.direction, k.knowledge_id, s.grimoire_id,
           COALESCE(NULLIF(btrim(k.name), ''), lk.label) AS label,
           lk.statement, lg.title AS book_title,
           COALESCE(btrim(lk.working), '') <> '' AS has_workings,
           em.qdrant_collection, em.vector_size, em.distance_metric
    FROM semantic_projection sp
    JOIN embedding e ON e.semantic_projection_id=sp.semantic_projection_id AND e.status='indexed'
    JOIN embedding_model em ON em.embedding_model_id=e.embedding_model_id AND em.is_active
    JOIN knowledge k ON k.knowledge_id=sp.knowledge_id AND k.is_active
    JOIN section s ON s.section_id=k.section_id
    JOIN grimoire g ON g.grimoire_id=s.grimoire_id
    JOIN language_knowledge lk ON lk.knowledge_id=k.knowledge_id AND lk.language_id=sp.language_id
    JOIN language_grimoire lg ON lg.grimoire_id=g.grimoire_id AND lg.language_id=sp.language_id
    WHERE sp.knowledge_id=ANY(%s) AND sp.is_active AND sp.direction='self'
      AND sp.projection_type IN ('statement','combined')
      AND sp.language_id=%s AND em.distance_metric='cosine' AND g.source_metadata->>'demo'='true'
    ORDER BY e.embedding_model_id, e.embedding_id
"""


def _pairs(rows: list[dict], model: int, collection: str, size: int) -> dict[int, dict[str, dict]]:
    by_object: dict[int, dict[str, dict]] = {}
    for row in rows:
        if (row['embedding_model_id'], row['qdrant_collection'], row['vector_size']) == (model, collection, size):
            by_object.setdefault(row['knowledge_id'], {}).setdefault(row['projection_type'], row)
    return by_object


def find_neighbors(knowledge_id: int, k: int) -> dict[str, Any]:
    """The k objects of every visible book nearest one object, by its stored projections.

    Since 0.0.19 its reach is bounded: PostgreSQL reads the source's own projections, Qdrant ranks the nearest
    points with the hidden books and the source left out by its filter, and PostgreSQL then reads only the
    hits' rows, again only from books the Web Demo shows. The earlier version read every eligible row of
    every visible book for each request.
    """
    with transaction() as (_, cur):
        cur.execute("""
            SELECT k.knowledge_id, s.grimoire_id, lk.language_id,
                   COALESCE(btrim(lk.working), '') <> '' AS has_workings
            FROM knowledge k JOIN section s ON s.section_id=k.section_id
            JOIN grimoire g ON g.grimoire_id=s.grimoire_id
            JOIN language_knowledge lk ON lk.knowledge_id=k.knowledge_id AND lk.language_id=1
            WHERE k.knowledge_id=%s AND k.is_active AND g.source_metadata->>'demo'='true'
        """, (knowledge_id,))
        source = cur.fetchone()
        if not source:
            raise HTTPException(404, 'Knowledge object not found')
        cur.execute(_PROJECTIONS_SQL, ([knowledge_id], source['language_id']))
        source_rows = list(cur.fetchall())
        scope = book_scope(cur)

    statement = next((r for r in source_rows if r['projection_type']=='statement'), None)
    if statement is None:
        raise HTTPException(409, 'Statement projection is missing')
    model, collection, size = statement['embedding_model_id'], statement['qdrant_collection'], statement['vector_size']
    source_pair = _pairs(source_rows, model, collection, size)[knowledge_id]
    if source['has_workings'] and 'combined' not in source_pair:
        raise HTTPException(409, 'Combined projection is missing despite available workings')
    projections = ('statement','combined') if source['has_workings'] else ('statement',)
    limit = min(256, k + 5)
    found: dict[str, dict[str, float]] = {}
    selected: set[int] = set()
    try:
        for projection in projections:
            hits = qdrant_service.query_raw(collection=collection, body={
                'query': source_pair[projection]['embedding_id'],
                'filter': scope_filter(scope, [
                    {'key': 'projection_type', 'match': {'value': projection}},
                    {'key': 'direction', 'match': {'value': 'self'}},
                    {'key': 'language_id', 'match': {'value': source['language_id']}},
                    {'key': 'is_active', 'match': {'value': True}},
                ], [{'key': 'knowledge_id', 'match': {'value': knowledge_id}}]),
                'limit': limit,
                'with_payload': ['knowledge_id'],
            })
            found[projection] = {}
            for hit in hits:
                try:
                    kid, score = int((hit.get('payload') or {})['knowledge_id']), float(hit['score'])
                except (KeyError, TypeError, ValueError):
                    continue
                if kid != knowledge_id:
                    found[projection][str(hit['id'])] = score
                    selected.add(kid)
    except (HTTPException, ValueError, TypeError) as exc:
        raise HTTPException(503, 'Neighbor retrieval is temporarily unavailable') from exc

    # Only the hits' rows, and the source's again: visibility can change while the vector service answers.
    with transaction() as (_, cur):
        cur.execute(_PROJECTIONS_SQL, (sorted(selected | {knowledge_id}), source['language_id']))
        by_object = _pairs(list(cur.fetchall()), model, collection, size)
    if knowledge_id not in by_object:
        raise HTTPException(404, 'Knowledge object not found')
    # A visible hit whose projections are incomplete is a processing fault, as before 0.0.19; only the hits
    # are looked at now, not every object of every book.
    faults = sum(1 for kid in selected if kid in by_object and (
        'statement' not in by_object[kid]
        or (by_object[kid]['statement']['has_workings'] and 'combined' not in by_object[kid])))
    candidates = {kid: pair for kid, pair in by_object.items() if kid != knowledge_id and kid in selected
                  and 'statement' in pair and (not pair['statement']['has_workings'] or 'combined' in pair)}
    # A score counts only for a point PostgreSQL says is that object's projection.
    scores: dict[str, dict[str, float]] = {
        projection: {pair[projection]['embedding_id']: found[projection][pair[projection]['embedding_id']]
                     for pair in candidates.values()
                     if projection in pair and pair[projection]['embedding_id'] in found[projection]}
        for projection in projections
    }
    try:
        for projection in projections:
            missing = [pair[projection]['embedding_id'] for pair in candidates.values()
                       if projection in pair and pair[projection]['embedding_id'] not in scores[projection]]
            if missing:
                hits = qdrant_service.query_candidates(collection=collection,
                    point_id=source_pair[projection]['embedding_id'], candidate_ids=missing, limit=len(missing))
                scores[projection].update({str(hit['id']): float(hit['score']) for hit in hits
                                           if str(hit['id']) in missing})
    except (HTTPException, ValueError, TypeError) as exc:
        raise HTTPException(503, 'Neighbor retrieval is temporarily unavailable') from exc
    results = []
    for kid, pair in candidates.items():
        row = pair['statement']
        s = scores['statement'].get(row['embedding_id'])
        c = scores.get('combined', {}).get(pair.get('combined', {}).get('embedding_id'))
        if s is None:
            continue
        try:
            score = combined_score(s, c, source['has_workings'], row['has_workings'])
        except (ValueError, TypeError):
            faults += 1
            continue
        results.append({key: row[key] for key in ('knowledge_id','grimoire_id','book_title','label','statement')}
                       | {'similarity_score': score})
    results.sort(key=lambda row: (-row['similarity_score'], row['knowledge_id']))
    return {'results': results[:k], 'scope': 'available_books', 'requested_k': k,
            'processing_faults': faults, 'score_scale': 'normalized_cosine'}
