"""Stored-projection discovery. PostgreSQL determines readable candidates."""
from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException

from ..database import transaction
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


def find_neighbors(knowledge_id: int, k: int) -> dict[str, Any]:
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
        cur.execute("""
            SELECT e.embedding_id::text, e.embedding_model_id, sp.projection_type,
                   sp.language_id, sp.direction, k.knowledge_id, s.grimoire_id,
                   lk.label, lk.statement, lg.title AS book_title,
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
            WHERE sp.is_active AND sp.direction='self' AND sp.projection_type IN ('statement','combined')
              AND sp.language_id=%s AND em.distance_metric='cosine' AND g.source_metadata->>'demo'='true'
            ORDER BY e.embedding_model_id, e.embedding_id
        """, (source['language_id'],))
        rows = list(cur.fetchall())

    source_rows = [r for r in rows if r['knowledge_id']==knowledge_id]
    statement = next((r for r in source_rows if r['projection_type']=='statement'), None)
    if statement is None:
        raise HTTPException(409, 'Statement projection is missing')
    model = statement['embedding_model_id']
    rows = [r for r in rows if r['embedding_model_id']==model
            and r['qdrant_collection']==statement['qdrant_collection']
            and r['vector_size']==statement['vector_size']]
    by_object: dict[int, dict[str, dict]] = {}
    for row in rows:
        by_object.setdefault(row['knowledge_id'], {}).setdefault(row['projection_type'], row)
    source_pair = by_object[knowledge_id]
    if source['has_workings'] and 'combined' not in source_pair:
        raise HTTPException(409, 'Combined projection is missing despite available workings')
    faults = sum('statement' not in pair or (next(iter(pair.values()))['has_workings'] and 'combined' not in pair)
                 for kid,pair in by_object.items() if kid != knowledge_id)
    candidates = {kid:pair for kid,pair in by_object.items() if kid!=knowledge_id and 'statement' in pair
                  and (not pair['statement']['has_workings'] or 'combined' in pair)}
    points = {row['embedding_id']: kid for kid,pair in candidates.items() for row in pair.values()}
    scores: dict[str, dict[str, float]] = {}
    selected: set[int] = set()
    try:
        for projection in ('statement','combined') if source['has_workings'] else ('statement',):
            ids = [pair[projection]['embedding_id'] for pair in candidates.values() if projection in pair]
            hits = qdrant_service.query_candidates(collection=statement['qdrant_collection'],
                point_id=source_pair[projection]['embedding_id'], candidate_ids=ids, limit=k)
            scores[projection] = {str(hit['id']): float(hit['score']) for hit in hits if str(hit['id']) in points}
            selected.update(points[pid] for pid in scores[projection])
        for projection in scores:
            missing = [candidates[kid][projection]['embedding_id'] for kid in selected
                       if projection in candidates[kid] and candidates[kid][projection]['embedding_id'] not in scores[projection]]
            if missing:
                hits = qdrant_service.query_candidates(collection=statement['qdrant_collection'],
                    point_id=source_pair[projection]['embedding_id'], candidate_ids=missing, limit=len(missing))
                scores[projection].update({str(hit['id']):float(hit['score']) for hit in hits if str(hit['id']) in missing})
    except (HTTPException, ValueError, TypeError) as exc:
        raise HTTPException(503, 'Neighbor retrieval is temporarily unavailable') from exc
    results=[]
    for kid in selected:
        pair=candidates[kid]; row=pair['statement']
        s=scores['statement'].get(row['embedding_id'])
        c=scores.get('combined',{}).get(pair.get('combined',{}).get('embedding_id'))
        try:
            score=combined_score(s,c,source['has_workings'],row['has_workings'])
        except (ValueError,TypeError):
            faults+=1
            continue
        results.append({key:row[key] for key in ('knowledge_id','grimoire_id','book_title','label','statement')} | {'similarity_score':score})
    results.sort(key=lambda row:(-row['similarity_score'],row['knowledge_id']))
    # Visibility can change while the vector service is answering. Recheck it
    # before returning any cached source labels or candidate text.
    with transaction() as (_, cur):
        cur.execute("""
            SELECT k.knowledge_id FROM knowledge k
            JOIN section s ON s.section_id=k.section_id
            JOIN grimoire g ON g.grimoire_id=s.grimoire_id
            WHERE k.knowledge_id=ANY(%s) AND k.is_active
              AND g.source_metadata->>'demo'='true'
        """, ([knowledge_id, *[row['knowledge_id'] for row in results]],))
        visible = {row['knowledge_id'] for row in cur.fetchall()}
    if knowledge_id not in visible:
        raise HTTPException(404, 'Knowledge object not found')
    results = [row for row in results if row['knowledge_id'] in visible]
    return {'results':results[:k], 'scope':'available_books', 'requested_k':k,
            'processing_faults':faults, 'score_scale':'normalized_cosine'}
