"""Package the saved Section Atlas sample for the existing Whole-book upload."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


PROTOTYPE = Path(__file__).resolve().parents[3] / "frontend/demo/prototypes/section-atlas.html"
SOURCE_KEY = "theumst-demo-section-atlas-real-analysis-v1"


def build_manifest():
    # Evaluate only the prototype's data declarations, without its UI or browser code.
    extractor = """
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(process.argv[1], 'utf8');
const start = html.indexOf('const hierarchy=');
const end = html.indexOf('const adjacency=', start);
if (start < 0 || end < start) throw new Error('Prototype data declarations not found');
const data = vm.runInNewContext(html.slice(start, end) + '\\n({ hierarchy, nodes, deps })', {}, { timeout: 1000 });
process.stdout.write(JSON.stringify(data));
"""
    result = subprocess.run(
        ["node", "-e", extractor, str(PROTOTYPE)],
        check=True, capture_output=True, encoding="utf-8",
    )
    sample = json.loads(result.stdout)
    assert len(sample["nodes"]) == 36 and len(sample["deps"]) == 42
    sections = []
    for key, section in sample["hierarchy"].items():
        parts = section["name"].split(" · ", 1)
        sections.append({
            "source_key": key,
            "parent_source_key": section["parent"],
            "section_number": parts[0] if len(parts) == 2 else "0",
            "section_name": parts[-1],
        })
    workings = {
        13: "Use uniform continuity from item 4, then apply the integrability criterion from item 12. These are two separate incoming dependencies.",
        15: "Compute the sum of the first n squares, divide by the appropriate power of n, then take the limit.",
    }
    objects = [{
        "source_key": f"item-{node['id']:02}",
        "section_source_key": node["section"],
        "type": node["type"],
        "label": node["title"],
        "statement": node["text"] + "\n\n$$" + node["math"] + "$$",
        "working": workings.get(node["id"], ""),
        "source_metadata": {"demo_order": node["id"], "order": [node["id"]], "prototype_item": node["id"]},
    } for node in sample["nodes"]]
    graph = {
        "contract_version": 1,
        "graph_revision": "section-atlas-sample-v1",
        "nodes": [{
            "knowledge_id": obj["source_key"],
            "object_source_key": obj["source_key"],
            "graph_role": "assessment" if obj["type"] == "exercise" else "backbone",
        } for obj in objects],
        "relations": [{
            "source_knowledge_id": f"item-{source:02}",
            "target_knowledge_id": f"item-{target:02}",
            "relation_type": "dependency",
        } for source, target in sample["deps"]],
    }
    return {
        "schema_version": 2,
        "book": {
            "source_key": SOURCE_KEY,
            "title": "Real Analysis (Demo Sample)",
            "publisher": "Theumst demo examples",
            "language_id": 1,
            "version": "1",
            "metadata": {
                "demo": True,
                "synthetic": True,
                "summary": "The 36-item Real Analysis sample from the Section Atlas discussion. Explore foundations, integration, differentiation, and sequences of functions through definitions, examples, theorems, and exercises. This is illustrative demo material, not a complete textbook.",
                "source_issue": "https://github.com/Christopher8187/product/issues/28",
                "prototype_path": "frontend/demo/prototypes/section-atlas.html",
                "prototype_sha256": hashlib.sha256(PROTOTYPE.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
            },
        },
        "sections": sections,
        "objects": objects,
        "knowledge_graph": graph,
        "embeddings": [],
        "images": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Destination ZIP archive")
    args = parser.parse_args()
    manifest = build_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    entry = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    with zipfile.ZipFile(args.output, "w") as archive:
        archive.writestr(entry, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    print(json.dumps({
        "archive": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "sections": len(manifest["sections"]), "objects": len(manifest["objects"]),
        "relations": len(manifest["knowledge_graph"]["relations"]),
    }))


if __name__ == "__main__":
    main()
