from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.helpers.config import get_settings
from src.routes import base, data , nlp
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.models.AssetModels import AssetModel
from src.stores.llm.LLMProviderFactory import LLMProviderFactory
from src.stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.stores.llm.templates.template_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    postgres_conn= f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(postgres_conn, echo=False)

    app.db_client = sessionmaker(app.db_engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize collections and indexes.
    await ProjectModel.create_instance(db_client=app.db_client)
    await ChunkModel.create_instance(db_client=app.db_client)
    await AssetModel.create_instance(db_client=app.db_client)

    llm_provider_factory = LLMProviderFactory(config=settings)
    vectordb_provider_factory = VectorDBProviderFactory(
        config=settings,
        db_client=app.db_client,
    )

    # Initialize LLM clients.
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANGUAGE,
        default_language=settings.DEFAULT_LANGUAGE
    )

    # Vector DB client
    app.vectordb_client = await vectordb_provider_factory.create(
        provider = settings.VECTOR_DB_BACKEND
    )
    await app.vectordb_client.connect()

    try:
        yield
    finally:
        await app.db_engine.dispose()
        await app.vectordb_client.disconnect()

app = FastAPI(lifespan=lifespan)

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
