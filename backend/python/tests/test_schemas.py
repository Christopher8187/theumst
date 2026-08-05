import pytest
from pydantic import ValidationError

from app.schemas import EmbeddingBatchInput, KnowledgeSubmission, QdrantSearchRequest


BASE = {
    "book": {"grimoire_id": 1},
    "section": {"section_id": 2},
    "knowledge": {
        "language_id": 1,
        "type": "definition",
        "statement": "group",
        "workings": "A set with an associative operation...",
    },
    "embeddings": [],
}


def test_submission_requires_book_and_section():
    with pytest.raises(ValidationError):
        KnowledgeSubmission.model_validate({"knowledge": BASE["knowledge"]})


def test_workings_alias_is_normalized_to_database_working():
    payload = KnowledgeSubmission.model_validate(BASE)
    assert payload.knowledge.working.startswith("A set")


def test_qdrant_search_requires_text_or_vector():
    with pytest.raises(ValidationError):
        QdrantSearchRequest.model_validate({})
    assert QdrantSearchRequest(query_text="group definition").limit == 10


def test_embedding_batch_requires_at_least_one_projection():
    with pytest.raises(ValidationError):
        EmbeddingBatchInput.model_validate({"language_id": 1, "embeddings": []})
