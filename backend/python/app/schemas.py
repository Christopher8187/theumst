from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator


class ProfileUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=320)
    alias: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class IdentifierRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class EmailVerificationResendRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class EmailChangeRequest(BaseModel):
    new_email: str = Field(min_length=3, max_length=320)
    current_password: str = Field(min_length=1, max_length=256)


class BookPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(default="Independent", max_length=500)
    isbn: str | None = Field(default=None, max_length=64)
    publish_date: str | None = Field(default=None, max_length=80)
    version: str | None = Field(default=None, max_length=120)
    source_key: str | None = Field(default=None, max_length=500)
    language_id: int = Field(default=1, gt=0)


class BookDemoVisibility(BaseModel):
    enabled: bool


class MediaPostPayload(BaseModel):
    request_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(default="", max_length=1000)
    body: str = Field(min_length=1, max_length=100_000)
    image_url: str | None = Field(default=None, max_length=2000)
    grimoire_id: int | None = Field(default=None, gt=0)
    status: Literal["draft", "published"] = "published"
    email_introduction: str = Field(default="", max_length=5000)
    announce: bool = False

    @model_validator(mode="after")
    def announcement_requires_published_copy(self) -> "MediaPostPayload":
        if self.announce and (self.status != "published" or not self.email_introduction.strip()):
            raise ValueError("An announcement requires a published post and an email introduction")
        return self


class NewsEmailPreview(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    email_introduction: str = Field(min_length=1, max_length=5000)


class SubscriptionUpdate(BaseModel):
    news: bool


class DemoAccessRequestPayload(BaseModel):
    message: str = Field(default="", max_length=1000)


class DemoReviewPayload(BaseModel):
    note: str = Field(default="", max_length=1000)


class DemoProgressPayload(BaseModel):
    completed: bool = True


class DemoStudyStatePayload(BaseModel):
    knowledge_id: int = Field(gt=0)
    realm: Literal['text', 'questions'] = 'text'


# A note's limits, the Web Demo's and the game's alike.
NOTE_TAG_MAX_CHARACTERS = 120
NOTE_CONTENT_MAX_CHARACTERS = 50_000


def _check_note_target(note_type: str, knowledge_id: int | None) -> None:
    if note_type == "attached" and knowledge_id is None:
        raise ValueError("Attached notes require a knowledge_id")
    if note_type == "scribble" and knowledge_id is not None:
        raise ValueError("Scribble notes cannot be attached to a knowledge object")


class DemoNotePayload(BaseModel):
    grimoire_id: int | None = Field(default=None, gt=0)
    knowledge_id: int | None = Field(default=None, gt=0)
    note_type: Literal["attached", "scribble"]
    tag: str = Field(default="", max_length=NOTE_TAG_MAX_CHARACTERS)
    content: str = Field(default="", max_length=NOTE_CONTENT_MAX_CHARACTERS)

    @model_validator(mode="after")
    def validate_note_target(self) -> "DemoNotePayload":
        _check_note_target(self.note_type, self.knowledge_id)
        return self


def _storable(value: str) -> str:
    # PostgreSQL text holds no NUL, and a lone surrogate cannot be encoded: refused as 422, not a 500.
    if "\x00" in value:
        raise ValueError("Text cannot contain the NUL character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must be valid Unicode") from None
    return value


class GameNoteCreate(BaseModel):
    """POST /api/game/grimoires/{id}/notes: a note in that book, checked as DemoNotePayload is."""

    knowledge_id: int | None = Field(default=None, gt=0)
    note_type: Literal["attached", "scribble"]
    tag: str = Field(default="", max_length=NOTE_TAG_MAX_CHARACTERS)
    content: str = Field(default="", max_length=NOTE_CONTENT_MAX_CHARACTERS)

    _storable_text = field_validator("tag", "content")(_storable)

    @model_validator(mode="after")
    def validate_note_target(self) -> "GameNoteCreate":
        _check_note_target(self.note_type, self.knowledge_id)
        return self


class GameNoteUpdate(BaseModel):
    """PUT /api/game/grimoires/{id}/notes/{note_id}: new text, sent with the updated_at it was read at."""

    tag: str = Field(max_length=NOTE_TAG_MAX_CHARACTERS)
    content: str = Field(max_length=NOTE_CONTENT_MAX_CHARACTERS)
    if_updated_at: AwareDatetime

    _storable_text = field_validator("tag", "content")(_storable)


class GameNoteDelete(BaseModel):
    """DELETE /api/game/grimoires/{id}/notes/{note_id}: sent with the updated_at it was read at."""

    if_updated_at: AwareDatetime


class SqlRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=200_000)


class StorageTextWrite(BaseModel):
    path: str
    content: str = ""


class StorageFolderCreate(BaseModel):
    path: str = ""
    name: str


class QdrantSearchRequest(BaseModel):
    query_text: str | None = Field(default=None, max_length=20_000)
    query_vector: list[float] | None = None
    limit: int = Field(default=10, ge=1, le=100)
    score_threshold: float | None = None
    filters: dict[str, str | int | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_query(self) -> "QdrantSearchRequest":
        if not self.query_text and not self.query_vector:
            raise ValueError("Provide query_text or query_vector")
        return self


class BookReference(BaseModel):
    grimoire_id: int | None = Field(default=None, gt=0)
    isbn: str | None = Field(default=None, max_length=64)
    publish_date: str | None = Field(default=None, max_length=80)
    version: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def require_identifier(self) -> "BookReference":
        if self.grimoire_id is None and not any((self.isbn, self.publish_date, self.version)):
            raise ValueError("book must contain grimoire_id or identifying book metadata")
        return self


class SectionReference(BaseModel):
    section_id: int | None = Field(default=None, gt=0)
    section_number: str | None = Field(default=None, max_length=160)
    parent_section: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_identifier(self) -> "SectionReference":
        if self.section_id is None and not self.section_number:
            raise ValueError("section must contain section_id or section_number")
        return self


class KnowledgeObjectInput(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    language_id: int = Field(default=1, gt=0)
    type: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1)
    working: str | None = None
    workings: str | None = None
    is_default_in_crystal: bool = True
    likes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_working(self) -> "KnowledgeObjectInput":
        if self.working is not None and self.workings is not None and self.working != self.workings:
            raise ValueError("working and workings disagree")
        if self.working is None:
            self.working = self.workings or ""
        return self


class EmbeddingModelInput(BaseModel):
    provider: str = Field(min_length=1, max_length=120)
    model_name: str = Field(min_length=1, max_length=240)
    model_revision: str = Field(default="", max_length=120)
    distance_metric: Literal["cosine", "dot", "euclid"] = "cosine"
    qdrant_collection: str | None = Field(default=None, max_length=240)


class SemanticEmbeddingInput(BaseModel):
    projection_type: str = Field(min_length=1, max_length=120)
    direction: Literal["self", "outward", "inward"]
    target_description: str = Field(min_length=1)
    embedding_text: str = Field(min_length=1)
    target_concepts: list[str] = Field(default_factory=list)
    expected_target_types: list[str] = Field(default_factory=list)
    specificity: Literal["specific", "conceptual", "broad"] = "conceptual"
    grounding_kind: Literal["explicit", "strong_inference", "speculative"] = "strong_inference"
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[Any] = Field(default_factory=list)
    structured_object: dict[str, Any] = Field(default_factory=dict)
    generation_model: str | None = None
    generation_prompt_version: str | None = None
    vector: list[float] = Field(min_length=1)
    model: EmbeddingModelInput

    def content_hash(self) -> str:
        raw = (self.embedding_text + "\n" + self.model_dump_json(exclude={"vector"})).encode("utf-8")
        return sha256(raw).hexdigest()


class EmbeddingBatchInput(BaseModel):
    language_id: int = Field(default=1, gt=0)
    embeddings: list[SemanticEmbeddingInput] = Field(min_length=1, max_length=200)


class KnowledgeSubmission(BaseModel):
    book: BookReference
    section: SectionReference
    knowledge: KnowledgeObjectInput
    embeddings: list[SemanticEmbeddingInput] = Field(default_factory=list, max_length=200)
