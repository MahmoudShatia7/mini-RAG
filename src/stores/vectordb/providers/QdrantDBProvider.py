from qdrant_client import models,QdrantClient
from ..VectorDBInterface import  VectorDBInterface
import logging
from ..VectorDBEnums import DistanceMethodEnums
from typing import List
from uuid import uuid4
from src.models.db_schemes.data_chunk import RetrievedDocument

class QdrantDBProvider (VectorDBInterface):

    def __init__(self, db_path: str, distance_method: str):
        
        self.client = None
        self.db_path = db_path
        self.distance_method = None

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE

        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        self.logger = logging.getLogger(__name__)

    def connect(self):
        self.client = QdrantClient(path = self.db_path)

    def disconnect(self):
        self.client = None

    def is_collection_existed(self, collection_name: str) -> bool:
         return self.client.collection_exists(collection_name=collection_name)
    
    def list_all_collections(self) -> list:
        return self.client.get_collections()
    
    def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)
    
    def delete_collection(self, collection_name: str):
        if self.is_collection_existed(collection_name) :
            return self.client.delete_collection(collection_name=collection_name)
        return False
        
    def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        if do_reset :
             
             _ = self.delete_collection(collection_name=collection_name)

        if not self.is_collection_existed(collection_name):
            _ = self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size = embedding_size,
                    distance = self.distance_method
                )
            )
            return True
        return False
    
    def insert_one(self, collection_name, text, vector, metadata = None, record_id = None):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Can not insert new record to non-existing collection: {collection_name}")
            return False
        try : 
            point_id = record_id or str(uuid4())
            _ = self.client.upsert(
                collection_name=collection_name,
                points =[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload = {
                            "text" : text,
                            "metadata": metadata
                        }
                    )
                ]
            )
        except Exception as e :
            self.logger.error(f"Error while inserting batch: {e}")
            return False

        return True
    
    def insert_many(self, collection_name, texts, vectors, metadata = None, record_id = None, batch_size = 50):
        if metadata is None:
            metadata = [None] * len(texts)
        if record_id is None :
            record_id = [None] * len(texts)

        for i in range(0,len(texts) , batch_size) :
            batch_end = i + batch_size
            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_record_ids = record_id[i:batch_end]
            
            batch_records = [
                models.PointStruct(
                    id=batch_record_ids[x] or str(uuid4()),
                    vector=batch_vectors[x],
                    payload = {
                        "text" : batch_texts[x],
                        "metadata": batch_metadata[x]
                    }
                )

                for x in range(len(batch_texts))
            ]
            try: 
                _ = self.client.upsert(
                    collection_name=collection_name,
                    points = batch_records,
                )
            except Exception as e :
                self.logger.error(f"Error while inserting batch: {e}")
                return False

        return True
    

    def search_by_vector(self, collection_name: str, vector: list, limit: int = 5):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Can not search non-existing collection: {collection_name}")
            return None
        
        results = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit
        )
        points = results.points if hasattr(results, "points") else results

        if not points:
            return None

        return [
            RetrievedDocument(
                text = r.payload.get("text"),
                score = r.score
            )
            for r in points
]
