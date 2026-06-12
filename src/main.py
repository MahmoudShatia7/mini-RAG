from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from src.helpers.config import get_settings
    from src.routes import base, data
    from src.models.ProjectModel import ProjectModel
    from src.models.ChunkModel import ChunkModel
    from src.models.AssetModels import AssetModel
except ModuleNotFoundError:
    # Allow running from inside src/ as `python main.py`
    from helpers.config import get_settings
    from routes import base, data
    from models.ProjectModel import ProjectModel
    from models.ChunkModel import ChunkModel
    from models.AssetModels import AssetModel

app = FastAPI()

@app.on_event("startup")
async def startup_db_client() :
    settings = get_settings()

    app.mongo_connection = AsyncIOMotorClient (settings.MONGODB_URL)
    app.db_client = app.mongo_connection[settings.MONGODB_DATABASE]
    
    # Initialize collections and indexes
    project_model = await ProjectModel.create_instance(db_client=app.db_client)
    chunk_model = await ChunkModel.create_instance(db_client=app.db_client)
    asset_model = await AssetModel.create_instance(db_client=app.db_client)



@app.on_event("shutdown")
async def shutdown_db_client() :
    app.mongo_connection.close()

app.include_router(base.base_router)
app.include_router(data.data_router)
