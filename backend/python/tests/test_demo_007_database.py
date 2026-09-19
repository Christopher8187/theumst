"""Real PostgreSQL checks for names, dependencies and independent collection removal."""
import os
from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from app.database import connect
from app.routers import demo
from app.services.book_ingestion import _upsert_book, _upsert_objects, _upsert_sections

pytestmark = pytest.mark.skipif(os.getenv('THEUMST_DATABASE_INTEGRATION') != '1', reason='requires disposable PostgreSQL')


def test_names_dependencies_and_collection_removal(monkeypatch):
    connection = connect()
    try:
        with connection.cursor() as cur:
            book, language = _upsert_book(cur, {'source_key': '__demo007_test__', 'title': 'Names', 'metadata': {'demo': True}})
            sections = _upsert_sections(cur, book, language, [{'source_key': 'one', 'section_number': '1', 'section_name': 'One'}])
            inputs = [{'source_key': f'n{i}', 'section_source_key': 'one', 'type': 'definition', 'label': f'Legacy {i}', 'statement': str(i),
                       'source_metadata': {'order': [i]}, **({'name': 'Named object'} if i == 1 else {})} for i in range(1, 4)]
            objects = _upsert_objects(cur, grimoire_id=book, language_id=language, sections=sections, objects=inputs)
            ids = [objects[f'n{i}']['knowledge_id'] for i in range(1, 4)]
            # A legacy producer omitting name must not erase the value on reimport.
            inputs[0].pop('name')
            repeated = _upsert_objects(cur, grimoire_id=book, language_id=language, sections=sections, objects=inputs)
            assert repeated['n1']['knowledge_id'] == ids[0]
            cur.execute('SELECT name FROM knowledge WHERE knowledge_id=%s', (ids[0],))
            assert cur.fetchone()['name'] == 'Named object'
            for n, node in enumerate(ids):
                cur.execute("INSERT INTO knowledge_graph_node(grimoire_id,knowledge_id,stable_knowledge_id,graph_role) VALUES(%s,%s,%s,'backbone')", (book, node, f'n{n}'))
            for source, target, relation in [(ids[0], ids[1], 'dependency'), (ids[2], ids[1], 'similarity'), (ids[1], ids[2], 'dependency')]:
                cur.execute('INSERT INTO knowledge_graph_edge(grimoire_id,source_knowledge_id,target_knowledge_id,relation_type) VALUES(%s,%s,%s,%s)', (book, source, target, relation))
            cur.execute('''INSERT INTO "user"(username,email,password_hash) VALUES('__demo007_test__','demo007@example.invalid','unused') RETURNING user_id''')
            user_id = cur.fetchone()['user_id']
            cur.execute('INSERT INTO user_grimoire(user_id,grimoire_id) VALUES(%s,%s)', (user_id, book))
            cur.execute('INSERT INTO demo_knowledge_progress(user_id,knowledge_id,completed) VALUES(%s,%s,true)', (user_id, ids[0]))

            @contextmanager
            def transaction():
                yield connection, cur

            monkeypatch.setattr(demo, 'transaction', transaction)
            monkeypatch.setattr(demo, '_demo_user', lambda request: {'user_id': user_id})
            result = demo.dependencies(ids[1], None)['results']
            assert [row['knowledge_id'] for row in result] == [ids[0]]
            assert result[0]['label'] == 'Named object'
            assert demo.get_grimoire_knowledge_detail(book, ids[1], None)['knowledge']['label'] == 'Legacy 2'
            note_payload = demo.DemoNotePayload(grimoire_id=book, knowledge_id=ids[0], note_type='attached', tag='saved', content='before removal')
            note_id = demo.create_note(note_payload, None)['note']['demo_note_id']
            assert demo.remove_grimoire(book, None)['ok']
            note_payload.content = 'after removal'
            assert demo.update_note(note_id, note_payload, None)['ok']
            listed = demo.list_notes(None, grimoire_id=book)['notes']
            assert listed[0]['content'] == 'after removal'
            assert listed[0]['knowledge_label'] == 'Named object'
            retarget = note_payload.model_copy(update={'knowledge_id': ids[1]})
            with pytest.raises(HTTPException) as error:
                demo.update_note(note_id, retarget, None)
            assert error.value.status_code == 404
            assert demo.delete_note(note_id, None)['ok']

            cur.execute('SELECT completed FROM demo_knowledge_progress WHERE user_id=%s AND knowledge_id=%s', (user_id, ids[0]))
            assert cur.fetchone()['completed'] is True
            cur.execute('SELECT count(*) AS count FROM user_grimoire WHERE user_id=%s AND grimoire_id=%s', (user_id, book))
            assert cur.fetchone()['count'] == 0
            cur.execute('UPDATE grimoire SET source_metadata=%s::jsonb WHERE grimoire_id=%s', ('{"demo":false}', book))
            with pytest.raises(HTTPException) as error:
                demo.dependencies(ids[1], None)
            assert error.value.status_code == 404
    finally:
        connection.rollback()
        connection.close()


def test_accepted_archive_preserves_real_analysis_identities():
    import importlib.util
    import json
    from pathlib import Path
    import zipfile
    from app.services.book_ingestion import _deactivate_book_state

    archive_dir = os.getenv('THEUMST_007_ARCHIVES')
    if not archive_dir:
        pytest.skip('set THEUMST_007_ARCHIVES to the generated Sanctuary archives')
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location('legacy_sample', root / 'backend/examples/real-analysis-demo/build_archive.py')
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    old = legacy.build_manifest()
    with zipfile.ZipFile(Path(archive_dir) / 'analysis.zip') as archive:
        new = json.loads(archive.read('manifest.json'))
    assert old['book']['source_key'] == new['book']['source_key']
    assert {s['source_key'] for s in old['sections']} == {s['source_key'] for s in new['sections']}
    assert {o['source_key'] for o in old['objects']} == {o['source_key'] for o in new['objects']}
    # Use the real import row operations in one rolled-back transaction.
    connection = connect()
    try:
        with connection.cursor() as cur:
            def apply(manifest):
                book, language = _upsert_book(cur, manifest['book'])
                _deactivate_book_state(cur, book)
                sections = _upsert_sections(cur, book, language, manifest['sections'])
                objects = _upsert_objects(cur, grimoire_id=book, language_id=language, sections=sections, objects=manifest['objects'])
                return book, sections, {k:v['knowledge_id'] for k,v in objects.items()}
            book, sections, objects = apply(old)
            cur.execute('SELECT user_id,knowledge_id,completed FROM demo_knowledge_progress WHERE knowledge_id=ANY(%s) ORDER BY user_id,knowledge_id', (list(objects.values()),))
            progress = cur.fetchall()
            cur.execute('SELECT user_id,current_knowledge_id,questions_knowledge_id FROM demo_study_state WHERE grimoire_id=%s ORDER BY user_id', (book,))
            positions = cur.fetchall()
            new_book, new_sections, new_objects = apply(new)
            assert (book, sections, objects) == (new_book, new_sections, new_objects)
            cur.execute('SELECT user_id,knowledge_id,completed FROM demo_knowledge_progress WHERE knowledge_id=ANY(%s) ORDER BY user_id,knowledge_id', (list(objects.values()),))
            assert cur.fetchall() == progress
            cur.execute('SELECT user_id,current_knowledge_id,questions_knowledge_id FROM demo_study_state WHERE grimoire_id=%s ORDER BY user_id', (book,))
            assert cur.fetchall() == positions
            cur.execute('SELECT count(*) AS n FROM knowledge WHERE knowledge_id=ANY(%s) AND is_active AND name IS NOT NULL', (list(objects.values()),))
            assert cur.fetchone()['n'] == 36
    finally:
        connection.rollback()
        connection.close()
