from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    role = Column(String, nullable=False, index=True)
    password = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class ERPState(Base):
    __tablename__ = "erp_state"

    id = Column(Integer, primary_key=True)
    payload = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_id = Column(String, nullable=False, index=True)
    record_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)
    actor_name = Column(String, nullable=False)
    actor_role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)