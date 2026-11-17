import uuid
from sqlalchemy import Column, String, Numeric, Integer, Text, DateTime, ForeignKey, func, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_number = Column(String(100), nullable=False, index=True)
    type = Column(String(20), nullable=False)  # STOCK_IN, STOCK_OUT
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    transaction_at = Column(DateTime(timezone=True), nullable=False)
    sync_status = Column(String(20), nullable=False, default="SYNCED")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('STOCK_IN', 'STOCK_OUT')", name="check_transaction_type"),
        CheckConstraint("sync_status IN ('PENDING', 'SYNCED', 'FAILED')", name="check_transaction_sync_status"),
        Index("idx_business_transaction_at", "business_id", "transaction_at"),
        Index("idx_business_type", "business_id", "type"),
    )

    # Relationships
    business = relationship("Business", back_populates="transactions")
    creator = relationship("User", back_populates="created_transactions")
    items = relationship("StockTransactionItem", back_populates="transaction", cascade="all, delete-orphan")


class StockTransactionItem(Base):
    __tablename__ = "stock_transaction_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("stock_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_cost_snapshot = Column(Numeric(12, 2), nullable=False, default=0.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_item_quantity_positive"),
        Index("idx_transaction_product", "transaction_id", "product_id"),
    )

    # Relationships
    transaction = relationship("StockTransaction", back_populates="items")
    product = relationship("Product", back_populates="transaction_items")
