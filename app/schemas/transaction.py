from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class TransactionItemCreate(BaseModel):
    product_id: UUID = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    quantity: int = Field(..., gt=0, example=5, description="Jumlah barang (harus lebih dari 0)")
    unit_cost_snapshot: Optional[Decimal] = Field(None, ge=0, example=8000.00, description="Snapshot harga modal saat transaksi")

class TransactionItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    product_unit: Optional[str] = None
    quantity: int
    unit_cost_snapshot: Decimal
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionCreate(BaseModel):
    id: Optional[UUID] = Field(None, description="UUID idempotent yang dibuat oleh aplikasi mobile offline")
    transaction_number: Optional[str] = Field(None, example="TBK-2026-0001", description="Nomor transaksi opsional dari client")
    type: str = Field(..., example="STOCK_IN", description="STOCK_IN atau STOCK_OUT")
    notes: Optional[str] = Field(None, example="Pembelian stok dari supplier Toko Makmur")
    transaction_at: Optional[datetime] = Field(None, description="Waktu kejadian di perangkat mobile")
    items: List[TransactionItemCreate] = Field(..., min_length=1, description="Daftar item barang dalam transaksi ini")

class TransactionResponse(BaseModel):
    id: UUID
    business_id: UUID
    transaction_number: str
    type: str
    notes: Optional[str]
    created_by: UUID
    transaction_at: datetime
    sync_status: str
    created_at: datetime
    items: List[TransactionItemResponse] = []

    class Config:
        from_attributes = True

class TransactionListResponse(BaseModel):
    total: int
    items: List[TransactionResponse]
