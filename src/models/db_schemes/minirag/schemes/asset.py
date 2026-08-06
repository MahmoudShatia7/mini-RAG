from .minirag_base import sqlalchemy_base
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID,JSONB
import uuid
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Index

class Asset(sqlalchemy_base):

    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_uuid = Column(UUID(as_uuid=True),nullable=False, unique=True, index=True, default=uuid.uuid4)

    asset_type = Column(String, nullable=False)
    asset_name = Column(String, nullable=False) 
    asset_size = Column(Integer, nullable=False)
    asset_config = Column(JSONB, nullable=True)

    asset_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)

    project = relationship("Project", back_populates="assets")
    chunks = relationship("DataChunk", back_populates="asset")

    __table_args__ = (
       Index('ix_asset_project_id', 'asset_project_id'),
       Index('ix_asset_type', 'asset_type'),
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(),nullable=True)
