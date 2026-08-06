from .BaseController import BaseController
from src.models.db_schemes import Project, DataChunk
from src.stores.llm.LLMEnums import DocumentTypeEnum
import json
import logging
import re

logger = logging.getLogger("uvicorn.error")

class NLPController (BaseController) :

    def __init__(self, vectordb_client, embedding_client, generation_client , template_parser=None) :
        super().__init__()

        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.generation_client = generation_client
        self.template_parser = template_parser
        self.logger = logger

    def create_collection_name (self, project_id: str) :
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
    
    async def reset_vector_db_collection(self, project : Project) :
        collection_name = self.create_collection_name(project_id = project.project_id)
        return await self.vectordb_client.delete_collection(collection_name =  collection_name)
    
    async def get_vector_db_collection_info(self, project: Project) :
        collection_name = self.create_collection_name(project_id = project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)

        return collection_info
    
    async def index_into_vector_db(
        self,
        project: Project,
        chunks: list[DataChunk],
        do_reset: bool = False,
    ):
        collection_name = self.create_collection_name(project_id = project.project_id)

        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]
        record_ids = [c.chunk_id for c in chunks]
        vectors = self.embedding_client.embed_texts(
            texts=texts,
            document_type=DocumentTypeEnum.DOCUMENT.value,
        )

        if isinstance(vectors, list) and vectors:
            first_item = vectors[0]
            if isinstance(first_item, (int, float)):
                vectors = [vectors]
            elif isinstance(first_item, list):
                vectors = vectors

        if not vectors or len(vectors) != len(texts):
            self.logger.error(
                "Embedding generation failed or returned a mismatched vector count "
                f"for collection {collection_name}."
            )
            return False

        _ = await self.vectordb_client.create_collection(
            collection_name= collection_name,
            embedding_size = self.embedding_client.embedding_size,
            do_reset = do_reset
        )

        is_inserted = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            vectors=vectors,
            metadata=metadata,
            record_id=record_ids,
        )
        
        return is_inserted
    
    async def search_vector_db_collection(self, project: Project, text: str, limit: int= 10):
        collection_name = self.create_collection_name(project_id = project.project_id)

        query_vector = None
        vector = self.embedding_client.embed_text(text=text,
                                                       document_type=DocumentTypeEnum.QUERY.value)


        if not vector or len(vector)==0 :
             return False

        if isinstance(vector, list):
            if vector and isinstance(vector[0], (int, float)):
                query_vector = vector
            elif len(vector) > 0 and isinstance(vector[0], list):
                query_vector = vector[0]

        if not query_vector:
             return False

        results = await self.vectordb_client.search_by_vector(
             collection_name= collection_name,
             vector=query_vector,
             limit=limit
        )

        if not results :
             return False

        return results

    def detect_query_language(self, query: str) -> str:
        if query and re.search(r"[\u0600-\u06FF]", query):
            return "ar"
        return self.template_parser.language if self.template_parser else "en"
    

    async def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        if not self.template_parser:
            self.logger.error("Template parser is not configured.")
            return None

        retrieved_documents = await self.search_vector_db_collection(project=project, text=query, limit=limit)

        if not retrieved_documents or len(retrieved_documents) == 0:
            return None
        
        response_language = self.detect_query_language(query=query)

        system_prompt = self.template_parser.get(
            group="rag",
            key="system_prompt",
            language=response_language
        )

        document_prompts = "\n.".join([
            self.template_parser.get(group="rag", key="document_prompt", vars={

                "document_number": idx + 1,
                "chunk_content": self.generation_client.process_text(doc.text),

            }, language=response_language)
            for idx, doc in enumerate(retrieved_documents)

        ])


        footer_prompt = self.template_parser.get(
            group="rag",
            key="footer_prompt",
            vars={"query": query},
            language=response_language
        )

        chat_history = [
                self.generation_client.construct_prompt(prompt=system_prompt, role=self.generation_client.enums.SYSTEM.value,)
        ]

        full_prompt = "\n\n".join([document_prompts, footer_prompt])

        answer = self.generation_client.generate_text(prompt=full_prompt, chat_history=chat_history)

        if not answer:
            return None

        return answer,full_prompt,chat_history
