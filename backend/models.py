import uuid
from sqlalchemy import Column, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    project_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    running_summary = Column(Text, nullable=True)

class ArchitectureReview(Base):
    __tablename__ = "architecture_reviews"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    project_id = Column(String, index=True)
    ratings = Column(JSON) # e.g. {"security": 8, "scalability": 7}
    recommendations = Column(JSON) # e.g. [{"category": "security", "text": "..."}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ArchitectureState(Base):
    __tablename__ = "architecture_states"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    project_id = Column(String, index=True)
    content = Column(Text) # Markdown content
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProjectConstraint(Base):
    __tablename__ = "project_constraints"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    project_id = Column(String, index=True)
    description = Column(String)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProjectArtifact(Base):
    __tablename__ = "project_artifacts"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    project_id = Column(String, index=True)
    pdf_id = Column(String, unique=True, index=True)
    filename = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
