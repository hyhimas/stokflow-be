from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from app.schemas.product import ProductCreate, ProductResponse
from app.schemas.transaction import TransactionCreate, TransactionResponse

class SyncPushRequest(BaseModel):
    products: List[ProductCreate] = Field(default=[], description="Antrean produk lokal berstatus PENDING")
    transactions: List[TransactionCreate] = Field(default=[], description="Antrean transaksi lokal berstatus PENDING")

class SyncPushResponse(BaseModel):
    synced_product_ids: List[UUID] = []
    synced_transaction_ids: List[UUID] = []
    failed_items: List[Dict[str, Any]] = []
    message: str = "Sinkronisasi selesai"

class SyncPullResponse(BaseModel):
    server_time: datetime
    products: List[ProductResponse]
    recent_transactions: List[TransactionResponse]
