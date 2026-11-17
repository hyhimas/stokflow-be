import uuid
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, func, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_barcode = Column(String(100), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    unit = Column(String(50), nullable=False)  # pcs, dus, kg, pack
    cost_price = Column(Numeric(12, 2), nullable=False, default=0.00)
    selling_price = Column(Numeric(12, 2), nullable=False, default=0.00)
    current_stock = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="ACTIVE")
    sync_status = Column(String(20), nullable=False, default="SYNCED")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("current_stock >= 0", name="check_product_current_stock_non_negative"),
        CheckConstraint("cost_price >= 0", name="check_product_cost_price_non_negative"),
        CheckConstraint("selling_price >= 0", name="check_product_selling_price_non_negative"),
        CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="check_product_status"),
        CheckConstraint("sync_status IN ('PENDING', 'SYNCED', 'FAILED')", name="check_product_sync_status"),
        Index("idx_business_sku_barcode", "business_id", "sku_barcode"),
        Index("idx_business_product_name", "business_id", "name"),
    )

    # Relationships
    business = relationship("Business", back_populates="products")
    transaction_items = relationship("StockTransactionItem", back_populates="product")
