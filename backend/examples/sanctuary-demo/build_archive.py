"""Package the accepted small books for idempotent upload through existing ingestion."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from urllib.parse import unquote_to_bytes
import base64

ROOT = Path(__file__).resolve().parents[3]


def build(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        exported = Path(temporary) / "books.json"
        subprocess.run(["node", str(Path(__file__).with_name("export.mjs")), str(exported)], check=True)
        fixtures = json.loads(exported.read_text(encoding="utf-8"))
    for fixture in fixtures:
        book = fixture["sample"]
        # Keep the identity of the existing Real Analysis upload.
        source_key = "theumst-demo-section-atlas-real-analysis-v1" if book["id"] == "analysis" else f"theumst-demo-{book['id']}-v1"
        section_keys = {section['section_id']: f"section-{section['section_id']}" for section in fixture['sections']}
        if book['id'] == 'analysis':
            original = json.loads((ROOT / 'frontend/demo/prototypes/tree-of-wisdom/text/study-fixtures-analysis.json').read_text())
            section_keys = dict(enumerate(original['hierarchy'], 1))
        sections = [{"source_key": section_keys[section['section_id']],
                     "parent_source_key": section_keys[section['parent_section']] if section['parent_section'] else None,
                     "section_number": section['section_number'], "section_name": section['section_name'],
                     "source_metadata": {"demo_order": order, "is_book_root": section.get('is_book_root', False)}}
                    for order, section in enumerate(fixture['sections'])]
        objects, images, files = [], [], {}
        for order, node in enumerate(fixture['nodes'], 1):
            key = f"item-{node['knowledge_id']:02}"
            objects.append({"source_key": key, "section_source_key": section_keys[node['section_id']],
                            "type": node['type'], "name": node['label'], "label": node['label'],
                            "statement": node['statement'], "working": node['working'],
                            "source_metadata": {"demo_order": order, "order": [order]}})
            for image in node.get('images', []):
                filename = image['source_image_id'] + '.svg'
                prefix, encoded = image['url'].split(',', 1)
                if not prefix.startswith('data:image/svg+xml'):
                    raise ValueError('Expected the accepted inline SVG image')
                archive_path = 'images/' + filename
                files[archive_path] = base64.b64decode(encoded) if ';base64' in prefix else unquote_to_bytes(encoded)
                images.append({**image, "archive_path": archive_path, "object_source_key": key,
                               "section_source_key": section_keys[node['section_id']]})
        manifest = {"schema_version": 2,
                    "book": {"source_key": source_key, "title": book['title'], "publisher": book.get('publisher'),
                             "language_id": 1, "version": book.get('version', '1'),
                             "metadata": {"demo": True, "synthetic": True, "summary": book['summary'],
                                          "presentation": {key: book[key] for key in ('short','subject','color','symbol')}}},
                    "sections": sections, "objects": objects, "images": images, "embeddings": [],
                    "knowledge_graph": {"contract_version": 1, "graph_revision": "sanctuary-0.0.7",
                                        "nodes": [{"knowledge_id": obj['source_key'], "object_source_key": obj['source_key'],
                                                   "graph_role": "assessment" if obj['type'] == 'exercise' else 'backbone'} for obj in objects],
                                        "relations": [{"source_knowledge_id": f"item-{edge['source_knowledge_id']:02}",
                                                       "target_knowledge_id": f"item-{edge['target_knowledge_id']:02}",
                                                       "relation_type": "dependency"} for edge in fixture['edges']]}}
        path = output / f"{book['id']}.zip"
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
            for name, data in files.items():
                archive.writestr(name, data)
        print(f"{path}: {len(objects)} objects, {len(sections)} sections")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    build(parser.parse_args().output)
