from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class ProductBase(BaseModel):
    sku_barcode: Optional[str] = Field(None, example="8992753123456", description="Kode Barcode atau SKU produk")
    name: str = Field(..., example="Kopi Susu Gula Aren 250ml")
    unit: str = Field(..., example="pcs", description="Satuan produk: pcs, dus, kg, pack, dll.")
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0, example=8000.00, description="Harga modal")
    selling_price: Decimal = Field(default=Decimal("0.00"), ge=0, example=15000.00, description="Harga jual")

class ProductCreate(ProductBase):
    id: Optional[UUID] = Field(None, description="UUID opsional yang dibuat oleh aplikasi mobile saat offline")
    current_stock: int = Field(default=0, ge=0, example=50, description="Stok awal produk")

class ProductUpdate(BaseModel):
    sku_barcode: Optional[str] = Field(None, example="8992753123456")
    name: Optional[str] = Field(None, example="Kopi Susu Gula Aren 250ml")
    unit: Optional[str] = Field(None, example="pcs")
    cost_price: Optional[Decimal] = Field(None, ge=0, example=8500.00)
    selling_price: Optional[Decimal] = Field(None, ge=0, example=16000.00)
    status: Optional[str] = Field(None, example="ACTIVE", description="ACTIVE atau ARCHIVED")

class ProductResponse(ProductBase):
    id: UUID
    business_id: UUID
    current_stock: int
    status: str
    sync_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProductListResponse(BaseModel):
    total: int = Field(..., description="Total seluruh produk yang cocok")
    page: int = Field(..., description="Halaman saat ini")
    size: int = Field(..., description="Jumlah item per halaman")
    total_pages: int = Field(..., description="Total jumlah halaman yang tersedia")
    items: List[ProductResponse]
