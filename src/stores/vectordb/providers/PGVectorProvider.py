import json
import logging
import re
from typing import List

from sqlalchemy import text as sql_text

from ..VectorDBEnums import DistanceMethodEnums
from ..VectorDBInterface import VectorDBInterface
from src.models.db_schemes import RetrievedDocument


class PGVectorProvider(VectorDBInterface):
    def __init__(
        self,
        db_client,
        default_vector_size: int = 786,
        distance_method: str = None,
        index_threshold: int = 100,
    ):
        self.db_client = db_client
        self.default_vector_size = default_vector_size
        self.distance_method = (distance_method or DistanceMethodEnums.COSINE.value).lower()
        self.index_threshold = index_threshold or 100
        self.logger = logging.getLogger("uvicorn.error")

    def _sanitize_identifier(self, value: str) -> str:
        if not value or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"Invalid SQL identifier: {value}")
        return value

    def _vector_literal(self, vector: List[float]) -> str:
        return "[" + ",".join(str(float(item)) for item in vector) + "]"

    def _score_expression(self, vector_literal: str) -> str:
        if self.distance_method == DistanceMethodEnums.DOT.value:
            return f"-(vector <#> '{vector_literal}'::vector)"
        return f"1 - (vector <=> '{vector_literal}'::vector)"

    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector;"))

    async def disconnect(self):
        pass

    async def is_collection_existed(self, collection_name: str) -> bool:
        collection_name = self._sanitize_identifier(collection_name)
        async with self.db_client() as session:
            result = await session.execute(
                sql_text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = :table_name
                    )
                    """
                ),
                {"table_name": collection_name},
            )
            return bool(result.scalar_one())

    async def list_all_collections(self) -> list:
        async with self.db_client() as session:
            result = await session.execute(
                sql_text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                    """
                )
            )
            return result.scalars().all()

    async def get_collection_info(self, collection_name: str) -> dict:
        collection_name = self._sanitize_identifier(collection_name)
        if not await self.is_collection_existed(collection_name):
            return None

        async with self.db_client() as session:
            count_result = await session.execute(
                sql_text(f"SELECT COUNT(*) FROM {collection_name}")
            )
            count = count_result.scalar_one()

            return {
                "status": "green",
                "points_count": count,
                "indexed_vectors_count": count,
                "collection_name": collection_name,
                "distance_method": self.distance_method,
                "vector_size": self.default_vector_size,
            }

    async def delete_collection(self, collection_name: str) -> bool:
        collection_name = self._sanitize_identifier(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text(f"DROP TABLE IF EXISTS {collection_name}"))
        return True

    async def create_collection(
        self, collection_name: str, embedding_size: int, do_reset: bool = False
    ):
        collection_name = self._sanitize_identifier(collection_name)

        if not embedding_size or int(embedding_size) <= 0:
            self.logger.error("A valid embedding size is required to create a PGVector collection.")
            return False

        if do_reset:
            await self.delete_collection(collection_name=collection_name)

        if await self.is_collection_existed(collection_name):
            return False

        async with self.db_client() as session:
            async with session.begin():
                await session.execute(
                    sql_text(
                        f"""
                        CREATE TABLE {collection_name} (
                            id SERIAL PRIMARY KEY,
                            text TEXT NOT NULL,
                            vector VECTOR({int(embedding_size)}) NOT NULL,
                            metadata JSONB DEFAULT '{{}}'::jsonb,
                            chunk_id INTEGER REFERENCES chunks(chunk_id) ON DELETE CASCADE
                        )
                        """
                    )
                )
        return True

    async def insert_one(
        self,
        collection_name: str,
        text: str,
        vector: List,
        metadata: dict = None,
        record_id: str = None,
    ):
        if record_id is None:
            self.logger.error("chunk_id is required when inserting into PGVector.")
            return False

        return await self.insert_many(
            collection_name=collection_name,
            texts=[text],
            vectors=[vector],
            metadata=[metadata or {}],
            record_id=[record_id],
            batch_size=1,
        )

    async def insert_many(
        self,
        collection_name: str,
        texts: list,
        vectors: List,
        metadata: list = None,
        record_id: list = None,
        batch_size: int = 50,
    ):
        collection_name = self._sanitize_identifier(collection_name)

        if not await self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return False

        if not record_id or len(record_id) != len(texts):
            self.logger.error("Valid chunk ids are required for PGVector inserts.")
            return False

        if metadata is None:
            metadata = [{} for _ in texts]

        try:
            async with self.db_client() as session:
                async with session.begin():
                    for i in range(0, len(texts), batch_size):
                        batch_texts = texts[i : i + batch_size]
                        batch_vectors = vectors[i : i + batch_size]
                        batch_metadata = metadata[i : i + batch_size]
                        batch_record_ids = record_id[i : i + batch_size]

                        for text, vector, item_metadata, chunk_id in zip(
                            batch_texts, batch_vectors, batch_metadata, batch_record_ids
                        ):
                            await session.execute(
                                sql_text(
                                    f"""
                                    INSERT INTO {collection_name} (text, vector, metadata, chunk_id)
                                    VALUES (:text, CAST(:vector AS vector), CAST(:metadata AS jsonb), :chunk_id)
                                    """
                                ),
                                {
                                    "text": text,
                                    "vector": self._vector_literal(vector),
                                    "metadata": json.dumps(item_metadata or {}),
                                    "chunk_id": chunk_id,
                                },
                            )
        except Exception as exc:
            self.logger.exception(f"Failed to insert vectors into {collection_name}: {exc}")
            return False
        return True

    async def search_by_vector(
        self, collection_name: str, vector: List, limit: int = 5
    ) -> List[RetrievedDocument]:
        collection_name = self._sanitize_identifier(collection_name)

        if not await self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return None

        vector_literal = self._vector_literal(vector)
        score_expression = self._score_expression(vector_literal)

        async with self.db_client() as session:
            result = await session.execute(
                sql_text(
                    f"""
                    SELECT text, {score_expression} AS score
                    FROM {collection_name}
                    ORDER BY vector <=> '{vector_literal}'::vector
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            records = result.mappings().all()

        if not records:
            return None

        return [
            RetrievedDocument(text=record["text"], score=float(record["score"]))
            for record in records
        ]
