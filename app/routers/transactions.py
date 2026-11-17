import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.user import User
from app.models.business import Business
from app.models.product import Product
from app.models.transaction import StockTransaction, StockTransactionItem
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionItemResponse,
    TransactionListResponse
)
from app.core.deps import get_current_user

router = APIRouter(prefix="/transactions", tags=["Transaksi Stok (Stock Transactions)"])

def generate_transaction_number(db: Session, business_id: UUID) -> str:
    """Format: [BUSINESS_CODE]-[TAHUN]-[NOMOR_URUT] (FR-16)"""
    business = db.query(Business).filter(Business.id == business_id).first()
    biz_code = business.code if business else "TRX"
    current_year = datetime.now(timezone.utc).year

    # Hitung jumlah transaksi tahun ini untuk bisnis ini
    count = db.query(func.count(StockTransaction.id)).filter(
        StockTransaction.business_id == business_id,
        func.extract('year', StockTransaction.created_at) == current_year
    ).scalar() or 0

    seq_number = str(count + 1).zfill(4)
    return f"{biz_code}-{current_year}-{seq_number}"

def format_transaction_response(trx: StockTransaction) -> TransactionResponse:
    item_responses = []
    for item in trx.items:
        prod = item.product
        item_responses.append(
            TransactionItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=prod.name if prod else None,
                product_sku=prod.sku_barcode if prod else None,
                product_unit=prod.unit if prod else None,
                quantity=item.quantity,
                unit_cost_snapshot=item.unit_cost_snapshot,
                created_at=item.created_at
            )
        )

    res = TransactionResponse.model_validate(trx)
    res.items = item_responses
    return res

@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Catat Transaksi Barang Masuk (STOCK_IN) atau Keluar (STOCK_OUT)",
    description="Mencatat transaksi stok secara atomik. Mencegah stok minus saat STOCK_OUT (FR-12, FR-13, FR-14, FR-15)."
)
def create_transaction(
    req: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    trx_type = req.type.upper()
    if trx_type not in ["STOCK_IN", "STOCK_OUT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipe transaksi harus 'STOCK_IN' atau 'STOCK_OUT'."
        )

    # 1. Idempotent check (jika id dikirim oleh mobile offline)
    if req.id:
        existing_trx = db.query(StockTransaction).filter(StockTransaction.id == req.id).first()
        if existing_trx:
            # Transaksi sudah tersimpan, langsung kembalikan (mencegah double-decrement)
            return format_transaction_response(existing_trx)

    # 2. Validasi stok untuk semua item
    product_map = {}
    for item in req.items:
        prod = db.query(Product).filter(
            Product.id == item.product_id,
            Product.business_id == current_user.business_id
        ).with_for_update().first()  # Row-level lock untuk konsistensi ACID

        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produk dengan ID {item.product_id} tidak ditemukan dalam bisnis Anda."
            )

        if trx_type == "STOCK_OUT":
            if prod.current_stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Stok tidak mencukupi untuk '{prod.name}'. "
                        f"Stok tersedia: {prod.current_stock} {prod.unit}, diminta keluar: {item.quantity} {prod.unit}. "
                        "Aturan bisnis: Stok tidak boleh bernilai minus."
                    )
                )

        product_map[item.product_id] = prod

    # 3. Buat header transaksi
    trx_id = req.id if req.id else uuid.uuid4()
    trx_number = req.transaction_number or generate_transaction_number(db, current_user.business_id)
    trx_at = req.transaction_at or datetime.now(timezone.utc)

    new_trx = StockTransaction(
        id=trx_id,
        business_id=current_user.business_id,
        transaction_number=trx_number,
        type=trx_type,
        notes=req.notes,
        created_by=current_user.id,
        transaction_at=trx_at,
        sync_status="SYNCED"
    )
    db.add(new_trx)
    db.flush()

    # 4. Buat items dan perbarui stok produk
    for item in req.items:
        prod = product_map[item.product_id]
        unit_cost = item.unit_cost_snapshot if item.unit_cost_snapshot is not None else prod.cost_price

        trx_item = StockTransactionItem(
            id=uuid.uuid4(),
            business_id=current_user.business_id,
            transaction_id=new_trx.id,
            product_id=prod.id,
            quantity=item.quantity,
            unit_cost_snapshot=unit_cost,
            created_at=trx_at
        )
        db.add(trx_item)

        # Update stok produk
        if trx_type == "STOCK_IN":
            prod.current_stock += item.quantity
        else:
            prod.current_stock -= item.quantity

    db.commit()
    db.refresh(new_trx)

    return format_transaction_response(new_trx)

@router.get(
    "",
    response_model=TransactionListResponse,
    summary="Riwayat Transaksi Stok, Pencarian & Filter",
    description="Melihat riwayat transaksi STOCK_IN dan STOCK_OUT dengan filter jenis transaksi, tanggal, produk, pencarian nomor transaksi/catatan, serta pengurutan ASC/DESC (FR-21, FR-22)."
)
def list_transactions(
    search: Optional[str] = Query(None, description="Pencarian nomor transaksi (contoh: TRX-2026-0001) atau catatan transaksi"),
    type: Optional[str] = Query(None, description="Filter jenis transaksi: STOCK_IN, STOCK_OUT, atau kosongkan untuk semua"),
    product_id: Optional[UUID] = Query(None, description="Filter riwayat transaksi untuk produk tertentu"),
    start_date: Optional[datetime] = Query(None, description="Filter tanggal mulai transaksi (ISO format: YYYY-MM-DDTHH:MM:SS)"),
    end_date: Optional[datetime] = Query(None, description="Filter tanggal akhir transaksi (ISO format: YYYY-MM-DDTHH:MM:SS)"),
    sort_by: Optional[str] = Query("transaction_at", description="Urutkan berdasarkan: transaction_at, created_at, transaction_number"),
    order: Optional[str] = Query("desc", description="Arah pengurutan: desc (terbaru dulu - default) atau asc (terlama dulu)"),
    page: int = Query(1, ge=1, description="Nomor halaman (mulai dari 1)"),
    size: int = Query(20, ge=1, le=100, description="Jumlah transaksi per halaman (default: 20, max: 100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(StockTransaction).filter(StockTransaction.business_id == current_user.business_id)

    # 1. Filter Tipe Transaksi (STOCK_IN / STOCK_OUT)
    if type and type.upper() in ["STOCK_IN", "STOCK_OUT"]:
        query = query.filter(StockTransaction.type == type.upper())

    # 2. Filter Berdasarkan Produk Tertentu
    if product_id:
        query = query.join(StockTransactionItem).filter(StockTransactionItem.product_id == product_id)

    # 3. Filter Rentang Waktu (Tanggal)
    if start_date:
        query = query.filter(StockTransaction.transaction_at >= start_date)
    if end_date:
        query = query.filter(StockTransaction.transaction_at <= end_date)

    # 4. Pencarian Nomor Transaksi atau Catatan
    if search and search.strip():
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                StockTransaction.transaction_number.ilike(search_filter),
                StockTransaction.notes.ilike(search_filter)
            )
        )

    # 5. Sorting (Ascending / Descending)
    sort_column_map = {
        "transaction_at": StockTransaction.transaction_at,
        "created_at": StockTransaction.created_at,
        "transaction_number": StockTransaction.transaction_number,
    }
    sort_column = sort_column_map.get(sort_by.lower() if sort_by else "transaction_at", StockTransaction.transaction_at)
    if order and order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # 6. Pagination
    total = query.count()
    offset = (page - 1) * size
    total_pages = (total + size - 1) // size if total > 0 else 1

    records = query.offset(offset).limit(size).all()

    return TransactionListResponse(
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
        items=[format_transaction_response(t) for t in records]
    )

@router.get(
    "/{id}",
    response_model=TransactionResponse,
    summary="Detail Riwayat Transaksi",
    description="Melihat rincian suatu transaksi beserta daftar item barangnya."
)
def get_transaction(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    trx = db.query(StockTransaction).filter(
        StockTransaction.id == id,
        StockTransaction.business_id == current_user.business_id
    ).first()

    if not trx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaksi tidak ditemukan."
        )

    return format_transaction_response(trx)
