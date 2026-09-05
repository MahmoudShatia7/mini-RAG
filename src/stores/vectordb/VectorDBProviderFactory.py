from .providers import QdrantDBProvider, PGVectorDBProvider
from .VectorDBEnums import VectorDBEnums
from src.controllers.BaseController import BaseController
from sqlalchemy.orm import sessionmaker

class VectorDBProviderFactory:
    def __init__(self, config , db_client: sessionmaker = None):
        self.config = config
        self.base_controller = BaseController()
        self.db_client = db_client

    async def create(self, provider: str):
        provider = provider.upper()
        index_threshold = self.config.PGVECTOR_INDEX_THRESHOLD

        if provider == VectorDBEnums.QDRANT.value:
            Qdrant_db_client = self.base_controller.get_database_path(db_name=self.config.VECTOR_DB_PATH)

            return QdrantDBProvider(
                db_client=Qdrant_db_client,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threshold=index_threshold,
            )

        if provider == VectorDBEnums.PGVECTOR.value:
            return PGVectorDBProvider(
                db_client=self.db_client,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threshold=index_threshold,
            )

        raise ValueError(f"Unsupported vector database provider: {provider}")
