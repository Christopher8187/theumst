import runpy
from pathlib import Path


def test_sample_uses_the_object_metadata_field_read_by_ingestion():
    builder = Path(__file__).resolve().parents[2] / "examples/real-analysis-demo/build_archive.py"
    manifest = runpy.run_path(str(builder))["build_manifest"]()
    assert len(manifest["objects"]) == 36
    assert len(manifest["knowledge_graph"]["relations"]) == 42
    for ordinal, obj in enumerate(manifest["objects"], 1):
        assert obj["source_metadata"] == {
            "order": [ordinal], "demo_order": ordinal, "prototype_item": ordinal,
        }
