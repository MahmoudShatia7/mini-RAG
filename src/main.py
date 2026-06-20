from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from src.helpers.config import get_settings
from src.routes import base, data
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.models.AssetModels import AssetModel
from src.stores.LLMProviderFactory import LLMProviderFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    app.mongo_connection = AsyncIOMotorClient (settings.MONGODB_URL)
    app.db_client = app.mongo_connection[settings.MONGODB_DATABASE]

    # Initialize collections and indexes.
    await ProjectModel.create_instance(db_client=app.db_client)
    await ChunkModel.create_instance(db_client=app.db_client)
    await AssetModel.create_instance(db_client=app.db_client)

    llm_provider_factory = LLMProviderFactory(config=settings)

    # Initialize LLM clients.
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

    try:
        yield
    finally:
        app.mongo_connection.close()


app = FastAPI(lifespan=lifespan)

app.include_router(base.base_router)
app.include_router(data.data_router)
