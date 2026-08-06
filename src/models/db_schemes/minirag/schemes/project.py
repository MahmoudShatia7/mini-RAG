from .minirag_base import sqlalchemy_base
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from sqlalchemy.orm import relationship


class Project(sqlalchemy_base):

    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True),nullable=False, unique=True, index=True, default=uuid.uuid4)

    assets = relationship("Asset", back_populates="project")
    chunks = relationship("DataChunk", back_populates="project")

    created_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(),nullable=True)

