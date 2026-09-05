from enum import Enum

class VectorDBEnums(Enum):
    QDRANT = "QDRANT"
    PGVECTOR = "PGVECTOR"


class DistanceMethodEnums(Enum):
    COSINE = "cosine"
    DOT = "dot"

class PgvectorSchemaEnums(Enum):
    ID = "id"
    METADATA = "metadata"
    TEXT = "text"
    CHUNK_ID = "chunk_id"
    _PREFIX = "pgvector_"
    VECTOR = "vector"

class PgvectorDistanceMethodEnums(Enum):
    COSINE = "vector_cosine_ops"
    DOT = "vector_ip_ops"

class PgvectorIndexTypeEnums(Enum):
    IVFFLAT = "ivfflat"
    HNSW = "hnsw"