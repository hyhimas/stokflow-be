import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="OWNER")
    status = Column(String(20), nullable=False, default="ACTIVE")
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('SUPER_ADMIN', 'OWNER', 'STAFF')", name="check_user_role"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="check_user_status"),
    )

    # Relationships
    business = relationship("Business", back_populates="users")
    created_transactions = relationship("StockTransaction", back_populates="creator")
