import json
import logging
import re
from typing import List

from sqlalchemy import text as sql_text

from ..VectorDBEnums import (
    DistanceMethodEnums,
    PgvectorDistanceMethodEnums,
    PgvectorIndexTypeEnums,
)
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

    def _is_dot(self) -> bool:
        return self.distance_method == DistanceMethodEnums.DOT.value

    def _vector_opclass(self) -> str:
        if self._is_dot():
            return PgvectorDistanceMethodEnums.DOT.value
        return PgvectorDistanceMethodEnums.COSINE.value

    def _distance_operator(self) -> str:
        """The pgvector operator the index is built on, so ORDER BY can use it."""
        return "<#>" if self._is_dot() else "<=>"

    def _score_expression(self) -> str:
        """Similarity score (higher is better) from the distance operator."""
        if self._is_dot():
            return "-(vector <#> CAST(:query_vector AS vector))"
        return "1 - (vector <=> CAST(:query_vector AS vector))"

    def _index_name(self, collection_name: str) -> str:
        return f"{collection_name}_vector_idx"

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

    async def is_index_existed(self, collection_name: str) -> bool:
        collection_name = self._sanitize_identifier(collection_name)
        index_name = self._index_name(collection_name)

        async with self.db_client() as session:
            result = await session.execute(
                sql_text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE schemaname = 'public' AND indexname = :index_name
                    )
                    """
                ),
                {"index_name": index_name},
            )
            return bool(result.scalar_one())

    async def create_vector_index(
        self,
        collection_name: str,
        index_type: str = PgvectorIndexTypeEnums.HNSW.value,
    ) -> bool:
        """Build the ANN index once the collection is large enough to need one.

        Below the threshold a sequential scan is both faster and exact, so the
        index is only worth its build cost past index_threshold rows.
        """
        collection_name = self._sanitize_identifier(collection_name)

        if await self.is_index_existed(collection_name):
            return False

        async with self.db_client() as session:
            count_result = await session.execute(
                sql_text(f"SELECT COUNT(*) FROM {collection_name}")
            )
            count = count_result.scalar_one()

        if count < self.index_threshold:
            return False

        index_name = self._index_name(collection_name)
        opclass = self._vector_opclass()

        self.logger.info("START: Creating vector index for collection: %s", collection_name)
        self.logger.debug(
            "index=%s type=%s opclass=%s rows=%s", index_name, index_type, opclass, count
        )

        try:
            async with self.db_client() as session:
                async with session.begin():
                    await session.execute(
                        sql_text(
                            f"CREATE INDEX {index_name} ON {collection_name} "
                            f"USING {index_type} (vector {opclass})"
                        )
                    )
        except Exception as exc:
            self.logger.exception(f"Failed to create vector index on {collection_name}: {exc}")
            return False

        # Refresh planner statistics: right after a bulk load autoanalyze may not
        # have run yet, and a stale row estimate leads to a poor plan choice.
        try:
            async with self.db_client() as session:
                await session.execute(sql_text(f"ANALYZE {collection_name}"))
                await session.commit()
        except Exception as exc:
            self.logger.warning(f"ANALYZE failed for {collection_name}: {exc}")

        self.logger.info("END: Created vector index for collection: %s", collection_name)
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
        build_index: bool = True,
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

        if build_index:
            await self.create_vector_index(collection_name=collection_name)
        return True

    async def search_by_vector(
        self, collection_name: str, vector: List, limit: int = 5
    ) -> List[RetrievedDocument]:
        collection_name = self._sanitize_identifier(collection_name)

        if not await self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return None

        score_expression = self._score_expression()
        distance_operator = self._distance_operator()

        async with self.db_client() as session:
            result = await session.execute(
                sql_text(
                    f"""
                    SELECT text, {score_expression} AS score
                    FROM {collection_name}
                    ORDER BY vector {distance_operator} CAST(:query_vector AS vector)
                    LIMIT :limit
                    """
                ),
                {"query_vector": self._vector_literal(vector), "limit": limit},
            )
            records = result.mappings().all()

        if not records:
            return None

        return [
            RetrievedDocument(text=record["text"], score=float(record["score"]))
            for record in records
        ]

    async def build_index(self, collection_name: str):
        return await self.create_vector_index(collection_name=collection_name)
