from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, default).split(",") if value.strip())


@dataclass(frozen=True)
class Settings:
    project_root: Path
    frontend_root: Path
    backend_root: Path
    webpage_dist: Path
    dashboard_dist: Path
    public_images: Path
    sql_dir: Path

    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_schema_startup_mode: str

    cookie_name: str
    session_days: int
    cookie_secure: bool
    cors_origins: tuple[str, ...]

    public_webpage_url: str
    password_reset_ttl_minutes: int
    email_verification_ttl_hours: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str
    smtp_starttls: bool
    smtp_use_ssl: bool

    server: str
    local_storage_dir: str

    qdrant_enabled: bool
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    qdrant_vector_size: int
    qdrant_distance: str
    qdrant_vectors_on_disk: bool

    demo_similarity_projections: tuple[str, ...]
    demo_similarity_max_k: int
    knowledge_graph_roles: tuple[str, ...]
    knowledge_relation_types: tuple[str, ...]
    knowledge_dag_relation_types: tuple[str, ...]

    embedding_api_url: str | None
    embedding_api_key: str | None
    embedding_model: str | None

    regular_read_page_size: int
    regular_read_max_page_size: int
    master_read_max_page_size: int

    @classmethod
    def from_environment(cls) -> "Settings":
        root = PROJECT_ROOT
        server = os.getenv("SERVER", "LOCAL").upper()
        schema_mode = os.getenv(
            "DB_SCHEMA_STARTUP_MODE",
            "disabled",
        ).strip().lower()
        if schema_mode not in {"disabled", "replay"}:
            raise ValueError("DB_SCHEMA_STARTUP_MODE must be disabled or replay")
        if server != "LOCAL" and schema_mode != "disabled":
            raise ValueError("Historical schema replay is forbidden outside LOCAL")
        qdrant_key = os.getenv("QDRANT_API_KEY") or None
        embedding_url = os.getenv("EMBEDDING_API_URL") or None
        embedding_key = os.getenv("EMBEDDING_API_KEY") or None
        embedding_model = os.getenv("EMBEDDING_MODEL") or None
        distance = os.getenv("QDRANT_DISTANCE", "cosine").strip().lower()
        if distance not in {"cosine", "dot", "euclid"}:
            raise ValueError("QDRANT_DISTANCE must be cosine, dot, or euclid")
        vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))
        if vector_size <= 0:
            raise ValueError("QDRANT_VECTOR_SIZE must be positive")
        similarity_projections = _csv(
            "DEMO_SIMILARITY_PROJECTIONS",
            "statement:self",
        )
        if not similarity_projections or any(":" not in value for value in similarity_projections):
            raise ValueError(
                "DEMO_SIMILARITY_PROJECTIONS must contain projection:direction entries"
            )
        similarity_max_k = int(os.getenv("DEMO_SIMILARITY_MAX_K", "25"))
        if not 1 <= similarity_max_k <= 100:
            raise ValueError("DEMO_SIMILARITY_MAX_K must be between 1 and 100")
        graph_roles = _csv(
            "KNOWLEDGE_GRAPH_ROLES",
            "unclassified,backbone,support,assessment,fragment,crosslink",
        )
        relation_types = _csv(
            "KNOWLEDGE_RELATION_TYPES",
            "depends_on,uses,proves,specialises,explains,examples,tests",
        )
        dag_relation_types = _csv(
            "KNOWLEDGE_DAG_RELATION_TYPES",
            "depends_on,uses,proves,specialises",
        )
        if not graph_roles or "unclassified" not in graph_roles:
            raise ValueError("KNOWLEDGE_GRAPH_ROLES must include unclassified")
        if not relation_types or not set(dag_relation_types).issubset(relation_types):
            raise ValueError(
                "KNOWLEDGE_DAG_RELATION_TYPES must be a subset of KNOWLEDGE_RELATION_TYPES"
            )

        return cls(
            project_root=root,
            frontend_root=root / "frontend",
            backend_root=root / "backend",
            webpage_dist=root / "frontend" / "webpage" / "dist",
            dashboard_dist=root / "frontend" / "dashboard" / "dist",
            public_images=root / "backend" / "assets" / "images",
            sql_dir=root / "backend" / "sql",
            db_name=os.getenv("DB_NAME", "theumst"),
            db_user=os.getenv("DB_USER", "postgres"),
            db_password=os.getenv("DB_PASSWORD", "postgres"),
            db_host=os.getenv("DB_HOST", "127.0.0.1"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_schema_startup_mode=schema_mode,
            cookie_name=os.getenv("SESSION_COOKIE", "theumst_session"),
            session_days=int(os.getenv("SESSION_DAYS", "7")),
            cookie_secure=_bool("COOKIE_SECURE", False),
            cors_origins=_csv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:5174,http://127.0.0.1:5174,"
                "http://localhost:8080,http://127.0.0.1:8080",
            ),
            public_webpage_url=os.getenv("PUBLIC_WEBPAGE_URL", "http://localhost:5173").rstrip("/"),
            password_reset_ttl_minutes=int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "60")),
            email_verification_ttl_hours=int(os.getenv("EMAIL_VERIFICATION_TTL_HOURS", "24")),
            smtp_host=os.getenv("SMTP_HOST", "").strip(),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "").strip(),
            smtp_from_name=os.getenv("SMTP_FROM_NAME", "theumst").strip() or "theumst",
            smtp_starttls=_bool("SMTP_STARTTLS", True),
            smtp_use_ssl=_bool("SMTP_USE_SSL", False),
            server=server,
            local_storage_dir=os.getenv("LOCAL_STORAGE_DIR", "__AUTO__"),
            qdrant_enabled=_bool("QDRANT_ENABLED", True),
            qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
            qdrant_api_key=qdrant_key,
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "knowledge-qwen3-embedding-0-6b"),
            qdrant_vector_size=vector_size,
            qdrant_distance=distance,
            qdrant_vectors_on_disk=_bool("QDRANT_VECTORS_ON_DISK", False),
            demo_similarity_projections=similarity_projections,
            demo_similarity_max_k=similarity_max_k,
            knowledge_graph_roles=graph_roles,
            knowledge_relation_types=relation_types,
            knowledge_dag_relation_types=dag_relation_types,
            embedding_api_url=embedding_url,
            embedding_api_key=embedding_key,
            embedding_model=embedding_model,
            regular_read_page_size=int(os.getenv("REGULAR_READ_PAGE_SIZE", "25")),
            regular_read_max_page_size=int(os.getenv("REGULAR_READ_MAX_PAGE_SIZE", "100")),
            master_read_max_page_size=int(os.getenv("MASTER_READ_MAX_PAGE_SIZE", "1000")),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
