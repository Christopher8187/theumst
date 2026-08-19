from __future__ import annotations

import hashlib
import sys
import types


# The execution sandbox does not ship several production-only wheels. Provide
# narrow import stubs so application structure and pure endpoint logic can be
# tested without pretending to exercise PostgreSQL or Qdrant themselves.
try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError:
    psycopg2 = types.ModuleType("psycopg2")
    class Error(Exception):
        pgcode = None
    class OperationalError(Error):
        pass
    psycopg2.Error = Error
    psycopg2.OperationalError = OperationalError
    psycopg2.connect = lambda *args, **kwargs: (_ for _ in ()).throw(OperationalError("stub"))
    extensions = types.ModuleType("psycopg2.extensions")
    extensions.connection = object
    extras = types.ModuleType("psycopg2.extras")
    extras.RealDictCursor = object
    def execute_values(cur, query, values, template=None, page_size=100):
        """Small test-only stand-in for psycopg2.extras.execute_values.

        Pure/unit tests only need imports to resolve; database-backed ingestion
        acceptance remains a container prerequisite and must use psycopg2.
        """
        cur.execute(query, values)
    extras.execute_values = execute_values
    sys.modules.update({
        "psycopg2": psycopg2,
        "psycopg2.extensions": extensions,
        "psycopg2.extras": extras,
    })

try:
    import passlib.context  # noqa: F401
except ModuleNotFoundError:
    passlib = types.ModuleType("passlib")
    context = types.ModuleType("passlib.context")
    class CryptContext:
        def __init__(self, *args, **kwargs):
            pass
        def hash(self, value):
            return "stub$" + hashlib.sha256(value.encode()).hexdigest()
        def verify(self, value, hashed):
            return hashed == self.hash(value)
    context.CryptContext = CryptContext
    passlib.context = context
    sys.modules.update({"passlib": passlib, "passlib.context": context})

try:
    import qdrant_client  # noqa: F401
except ModuleNotFoundError:
    qdrant_client = types.ModuleType("qdrant_client")
    models = types.ModuleType("qdrant_client.models")

    class _Enum:
        COSINE = "cosine"
        DOT = "dot"
        EUCLID = "euclid"
        INTEGER = "integer"
        KEYWORD = "keyword"
        BOOL = "bool"

    class _Container:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    models.Distance = _Enum
    models.PayloadSchemaType = _Enum
    for name in ("VectorParams", "PointStruct", "MatchValue", "FieldCondition", "Filter"):
        setattr(models, name, type(name, (_Container,), {}))

    class QdrantClient:
        def __init__(self, *args, **kwargs):
            pass

    qdrant_client.QdrantClient = QdrantClient
    qdrant_client.models = models
    sys.modules.update({"qdrant_client": qdrant_client, "qdrant_client.models": models})
