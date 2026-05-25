from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
import os
import aiofiles
import logging
from .schemes.data import ProcessRequest


logger = logging.getLogger('uvicorn.error')
try:
    from src.models import ResponseSignal
    from src.helpers.config import get_settings, settings
    from src.controllers import DataController, ProjectController, ProcessControllers
except ModuleNotFoundError:
    from models import ResponseSignal
    from helpers.config import get_settings, settings
    from controllers import DataController, ProjectController, ProcessControllers


data_router = APIRouter(
    tags=["api_v1", "data"],
    prefix="/api/v1/data",
)


@data_router.post("/upload/{project_id}")
async def upload_data(
    project_id: str,
    file: UploadFile,
    app_settings: settings = Depends(get_settings),
):
    data_controller = DataController()
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid: 
        return JSONResponse (
            status_code=status.HTTP_400_BAD_REQUEST,    
            content= {
                "signal" : result_signal
            }
        )


    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename,
        project_id=project_id
    )

    try :
            

            async with aiofiles.open(file_path , "wb") as f :
                while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                    await f.write(chunk)
    except Exception as e :
         
         logger.error(f"Error While Uploading File: {e}")
         
         return JSONResponse (
            status_code=status.HTTP_400_BAD_REQUEST,    
            content= {
                "signal" : ResponseSignal.FILE_UPLOADED_FAILED.value
            }
        )


    return JSONResponse (
    content= {
        "signal" : ResponseSignal.FILE_UPLOADED_PASSED.value,
        "file_id" : file_id
             }
                        )


@data_router.post("/process/{project_id}")
async def process_endpoint(project_id: str, process_request: ProcessRequest):
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlab_size
    do_reset = process_request.do_reset
    _ = do_reset

    process_controller = ProcessControllers(project_id=project_id)

    try:
        file_content = process_controller.get_file_content(file_id=file_id)
        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )
    except Exception as e:
        logger.error(f"Error while processing file: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROCESSINF_FAILD.value},
        )

    if file_chunks is None or len(file_chunks) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROCESSINF_FAILD.value},
        )

    serializable_chunks = [
        {"page_content": chunk.page_content, "metadata": chunk.metadata}
        for chunk in file_chunks
    ]
    return JSONResponse(
        content={
            "signal": ResponseSignal.PROCESSING_SUCESS.value,
            "chunks": serializable_chunks,
        }
    )

