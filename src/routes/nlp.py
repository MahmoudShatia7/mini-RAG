from fastapi import APIRouter, status , Request
from fastapi.encoders import jsonable_encoder
from src.routes.schemes.nlp import PushRequest, SearchRequest
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.controllers import NLPController
from fastapi.responses import JSONResponse
from src.models import ResponseSignal
import logging
import sys
from tqdm import tqdm

logger = logging.getLogger('uvicorn.error')

# Fallback page size when the embedding provider declares no batch size.
DEFAULT_CHUNK_PAGE_SIZE = 50

nlp_router = APIRouter(
    prefix = "/api/v1/nlp",
    tags = ["api_v1" , "nlp"],
)

@nlp_router.post("/index/push/{project_id}")

async def index_project(request : Request , project_id : int , push_request : PushRequest) :
    try:
        project_model = await ProjectModel.create_instance(
            db_client=request.app.db_client
        )

        chunk_model = await ChunkModel.create_instance(
            db_client=request.app.db_client
        )
        project = await project_model.get_project_or_create_one(
            project_id=project_id
        )

        if not project :
            return JSONResponse(

                status_code = status.HTTP_400_BAD_REQUEST,
                content = {
                    "signal" : ResponseSignal.PROJECT_NOT_FOUND_ERROR.value
                }
            )
        
        nlp_controllers = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client= request.app.embedding_client,
            template_parser= request.app.template_parser,
        )

        has_records = True

        page_no = 1
        inserted_items_count = 0

        # Page chunks in whatever batch the embedding client is configured for,
        # otherwise a smaller page caps the batch and wastes provider calls.
        page_size = getattr(
            request.app.embedding_client, "default_embedding_batch_size", None
        ) or DEFAULT_CHUNK_PAGE_SIZE
        collection_name = nlp_controllers.create_collection_name(project_id=project.project_id)

        _ = await nlp_controllers.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=request.app.embedding_client.embedding_size,
            do_reset=push_request.do_reset
        )

        total_chunks_count = await chunk_model.get_project_chunk_count(project_id=project.project_id)
        logger.info(
            "Indexing project %s: %s chunks -> %s",
            project.project_id,
            total_chunks_count,
            collection_name,
        )
        pbar = tqdm(
            total=total_chunks_count,
            desc="Vector Indexing",
            position=0,
            unit="chunk",
            file=sys.stderr,
            dynamic_ncols=True,
            leave=True,
            mininterval=0.2,
        )


        try:
            while has_records :
                page_chunks = await chunk_model.get_project_chunk(project_id=project.project_id, page_no=page_no, page_size=page_size)
                if len(page_chunks) :
                    page_no +=1
                
                if not page_chunks or len (page_chunks) == 0 :
                    has_records = False
                    break

                is_inserted = await nlp_controllers.index_into_vector_db(
                    project=project,
                    chunks=page_chunks,
                    do_reset=False,
                    # Bulk load first; the ANN index is built once at the end so
                    # the remaining rows are not inserted into a live graph.
                    build_index=False,
                )

                if not is_inserted :
                    logger.error(
                        "Indexing failed for project %s after %s / %s chunks.",
                        project.project_id,
                        inserted_items_count,
                        total_chunks_count,
                    )
                    return JSONResponse(
                        status_code = status.HTTP_502_BAD_GATEWAY,
                    content = {
                        "signal" : ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value,
                        "inserted_items_count" : inserted_items_count,
                        "total_chunks_count" : total_chunks_count
                    }
                    )

                pbar.update(len(page_chunks))
                inserted_items_count += len(page_chunks)
        finally:
            pbar.close()

        if inserted_items_count:
            await nlp_controllers.build_vector_db_index(project=project)

        logger.info(
            "Indexed %s chunks for project %s.",
            inserted_items_count,
            project.project_id,
        )
            
        return JSONResponse(
            content = {
                    "signal" : ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS.value,
                    "inserted_items_count" : inserted_items_count
                }
        )
    except Exception as exc:
        logger.exception("Unexpected error while pushing chunks into the vector DB.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value}
        )

@nlp_router.get("/index/info/{project_id}")
async def get_index_info(request : Request , project_id : int) :
    try:
        project_model = await ProjectModel.create_instance(
            db_client=request.app.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=project_id
        )

        nlp_controllers = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client= request.app.embedding_client,
            template_parser = request.app.template_parser,
        )

        collection_info = await nlp_controllers.get_vector_db_collection_info(project=project)

        return JSONResponse(
            content = {
                    "signal" : ResponseSignal.VECTORDB_COLLECTION_RETRIVED.value,
                    "collection_info" : jsonable_encoder(collection_info)
                }
        )
    except Exception:
        logger.exception("Unexpected error while retrieving vector DB collection info.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value}
        )

@nlp_router.post("/index/search/{project_id}")
async def search_index(request : Request , project_id : int, search_request: SearchRequest) :
    try:
        project_model = await ProjectModel.create_instance(
            db_client=request.app.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=project_id
        )

        nlp_controllers = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client= request.app.embedding_client,
            template_parser = request.app.template_parser,
        )

        results = await nlp_controllers.search_vector_db_collection(
            project=project , text = search_request.text, limit= search_request.limit
        )

        if not results :

            return JSONResponse(
                status_code = status.HTTP_400_BAD_REQUEST,
                content = {
                    "signal" : ResponseSignal.VECTORDB_SEARCH_ERROR.value
                }
            )
        
        return JSONResponse(
            content = {
                    "signal" : ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
                    "results" : jsonable_encoder(results)
                }
        )
    except Exception:
        logger.exception("Unexpected error while searching the vector DB.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value}
        )


@nlp_router.post("/index/answer/{project_id}")
async def answer_rag_question(request : Request , project_id : int, search_request: SearchRequest) :
    try:
        project_model = await ProjectModel.create_instance(
            db_client=request.app.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=project_id
        )

        nlp_controllers = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client= request.app.embedding_client,
            template_parser = request.app.template_parser,
        )

        answer_result = await nlp_controllers.answer_rag_question(
            project=project , query = search_request.text, limit= search_request.limit
        )

        if not answer_result :

            return JSONResponse(
                status_code = status.HTTP_400_BAD_REQUEST,
                content = {
                    "signal" : ResponseSignal.RAG_ANSWER_ERROR.value
                }
            )

        answer, full_prompt, chat_history = answer_result
        
        return JSONResponse(
            content = {
                    "signal" : ResponseSignal.RAG_ANSWER_SUCCESS.value,
                    "answer" : answer,
                    "full_prompt" : full_prompt,
                    "chat_history" : chat_history
                }
        )
    except Exception:
        logger.exception("Unexpected error while generating RAG answer.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.RAG_ANSWER_ERROR.value}
        )
