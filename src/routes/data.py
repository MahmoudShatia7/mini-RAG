from fastapi import APIRouter, Depends, File, UploadFile, status , Request
from fastapi.responses import JSONResponse
import os
import aiofiles
import logging
from .schemes.data import ProcessRequest

logger = logging.getLogger('uvicorn.error')
try:
    from src.models import ResponseSignal
    from src.models.db_schemes import Asset, DataChunk
    from src.models.AssetModels import AssetModel
    from src.models.AssetTypeEnum import AssetTypeEnum
    from src.models.ChunkModel import ChunkModel
    from src.models.ProjectModel import ProjectModel
    from src.helpers.config import get_settings, settings
    from src.controllers import DataController, ProjectController, ProcessControllers
except ModuleNotFoundError:
    from models import ResponseSignal
    from models.db_schemes import DataChunk , Asset
    from models.ChunkModel import ChunkModel
    from models.AssetModels import AssetModel
    from models.AssetTypeEnum import AssetTypeEnum
    from models.ProjectModel import ProjectModel
    from helpers.config import get_settings, settings
    from controllers import DataController, ProjectController, ProcessControllers


data_router = APIRouter(
    tags=["api_v1", "data"],
    prefix="/api/v1/data",
)


@data_router.post("/upload/{project_id}")
async def upload_data(
    request : Request ,
    project_id: str,
    file: UploadFile = File(...),
    app_settings: settings = Depends(get_settings),
):
    
    project_model = ProjectModel(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

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
    

    # store asset metadata in the database
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    asset_resource = Asset(
        asset_project_id=project.id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size = os.path.getsize(file_path),
    )

    asset_record= await asset_model.create_asset(asset=asset_resource)



    return JSONResponse (
    content= {
        "signal" : ResponseSignal.FILE_UPLOADED_PASSED.value,
        "file_id" : file_id,
        "asset_id": str(asset_record.id),
        "project_id": str(project.id)
             }
                        )


@data_router.post("/process/{project_id}")
async def process_endpoint(request : Request,project_id: str, process_request: ProcessRequest):


    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset
    _ = do_reset


    project_model = ProjectModel(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    process_controller = ProcessControllers(project_id=project_id)


    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    project_files_ids = {}
    if process_request.file_id :
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.id,
            asset_name=process_request.file_id
        )

        if asset_record is None:
            try:
                asset_record = await asset_model.get_asset_by_id(process_request.file_id)
            except Exception:
                asset_record = None

        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseSignal.FILE_ID_ERROR.value},
            )

        project_files_ids = {asset_record.id: asset_record.asset_name}
    else :
        project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value
        )

        project_files_ids = {
            record.id: record.asset_name
            for record in project_files
        }

        if len(project_files_ids) == 0:
            project_files_ids = {
                None: file_name
                for file_name in os.listdir(process_controller.project_path)
                if os.path.isfile(os.path.join(process_controller.project_path, file_name))
            }

    if len(project_files_ids) == 0 :
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.NO_FILES_ERROR.value},
        )


    no_records = 0
    no_files = len(project_files_ids)

    chunk_model = ChunkModel(
        db_client=request.app.db_client
    )

    if do_reset ==1 :
        _ = await chunk_model.delete_chunk_by_project_id(
            project_id=project.id
        )

        
    all_file_chunks = []
    file_chunks_records = []
    for asset_id, file_id in project_files_ids.items():
        try:
            file_content = process_controller.get_file_content(file_id=file_id)

            if file_content is None:
                logger.warning(f"File {file_id} not found for processing.")
                continue
            
            file_chunks = process_controller.process_file_content(
                file_content=file_content,
                file_id=file_id,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )
        except Exception as e:
            logger.error(f"Error while processing file {file_id}: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseSignal.PROCESSINF_FAILD.value},
            )

        file_chunks = file_chunks or []
        all_file_chunks.extend(file_chunks)
        file_chunks_records.extend(
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.id,
                chunk_asset_id=asset_id,
            )
            for i, chunk in enumerate(file_chunks)
        )

    if len(all_file_chunks) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROCESSINF_FAILD.value},
        )

    no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)

    serializable_chunks = [
        {"page_content": chunk.page_content, "metadata": chunk.metadata}
        for chunk in all_file_chunks
    ]
    return JSONResponse(
        content={
            "signal": ResponseSignal.PROCESSING_SUCESS.value,
            "inserted_chunks": no_records,
            "chunks": serializable_chunks,
            "no_files": no_files,
        }
    )
