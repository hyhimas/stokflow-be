import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.transaction import StockTransaction, StockTransactionItem
from app.schemas.sync import SyncPushRequest, SyncPushResponse, SyncPullResponse
from app.schemas.product import ProductResponse
from app.routers.transactions import format_transaction_response, generate_transaction_number
from app.core.deps import get_current_user

router = APIRouter(prefix="/sync", tags=["Offline-First & Sinkronisasi Cloud (Sync)"])

@router.post(
    "/push",
    response_model=SyncPushResponse,
    summary="Sinkronisasi Data Antrean Offline (Push)",
    description="Menerima antrean master produk & transaksi berstatus PENDING dari SQLite/Drift perangkat saat kembali online (FR-18, FR-19, FR-20)."
)
def sync_push(
    req: SyncPushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    synced_product_ids = []
    synced_trx_ids = []
    failed_items = []

    # 1. Proses Master Produk yang dibuat saat offline
    for prod_req in req.products:
        prod_id = prod_req.id or uuid.uuid4()
        try:
            existing = db.query(Product).filter(Product.id == prod_id).first()
            if existing:
                # Sudah tersinkron sebelumnya (idempotent)
                synced_product_ids.append(prod_id)
                continue

            # Cek barcode duplikat
            if prod_req.sku_barcode and prod_req.sku_barcode.strip():
                dup = db.query(Product).filter(
                    Product.business_id == current_user.business_id,
                    Product.sku_barcode == prod_req.sku_barcode.strip(),
                    Product.status == "ACTIVE"
                ).first()
                if dup:
                    failed_items.append({
                        "type": "product",
                        "id": str(prod_id),
                        "reason": f"Barcode {prod_req.sku_barcode} sudah terdaftar pada produk {dup.name}"
                    })
                    continue

            new_prod = Product(
                id=prod_id,
                business_id=current_user.business_id,
                sku_barcode=prod_req.sku_barcode.strip() if prod_req.sku_barcode else None,
                name=prod_req.name.strip(),
                unit=prod_req.unit.strip(),
                cost_price=prod_req.cost_price,
                selling_price=prod_req.selling_price,
                current_stock=prod_req.current_stock,
                status="ACTIVE",
                sync_status="SYNCED"
            )
            db.add(new_prod)
            db.commit()
            synced_product_ids.append(prod_id)
        except Exception as e:
            db.rollback()
            failed_items.append({
                "type": "product",
                "id": str(prod_id),
                "reason": str(e)
            })

    # 2. Proses Transaksi Stok yang dibuat saat offline
    for trx_req in req.transactions:
        trx_id = trx_req.id or uuid.uuid4()
        try:
            existing_trx = db.query(StockTransaction).filter(StockTransaction.id == trx_id).first()
            if existing_trx:
                # Idempotent: Transaksi ini sudah pernah masuk server
                synced_trx_ids.append(trx_id)
                continue

            trx_type = trx_req.type.upper()
            if trx_type not in ["STOCK_IN", "STOCK_OUT"]:
                failed_items.append({
                    "type": "transaction",
                    "id": str(trx_id),
                    "reason": "Tipe transaksi harus STOCK_IN atau STOCK_OUT"
                })
                continue

            # Validasi stok produk
            product_map = {}
            has_stock_error = False
            for item in trx_req.items:
                p = db.query(Product).filter(
                    Product.id == item.product_id,
                    Product.business_id == current_user.business_id
                ).with_for_update().first()

                if not p:
                    failed_items.append({
                        "type": "transaction",
                        "id": str(trx_id),
                        "reason": f"Produk ID {item.product_id} tidak ditemukan"
                    })
                    has_stock_error = True
                    break

                if trx_type == "STOCK_OUT" and p.current_stock < item.quantity:
                    failed_items.append({
                        "type": "transaction",
                        "id": str(trx_id),
                        "reason": f"Stok tidak cukup untuk {p.name} (Tersedia: {p.current_stock}, Diminta: {item.quantity})"
                    })
                    has_stock_error = True
                    break

                product_map[item.product_id] = p

            if has_stock_error:
                db.rollback()
                continue

            # Buat transaksi
            trx_number = trx_req.transaction_number or generate_transaction_number(db, current_user.business_id)
            trx_at = trx_req.transaction_at or datetime.now(timezone.utc)

            new_trx = StockTransaction(
                id=trx_id,
                business_id=current_user.business_id,
                transaction_number=trx_number,
                type=trx_type,
                notes=trx_req.notes,
                created_by=current_user.id,
                transaction_at=trx_at,
                sync_status="SYNCED"
            )
            db.add(new_trx)
            db.flush()

            for item in trx_req.items:
                p = product_map[item.product_id]
                unit_cost = item.unit_cost_snapshot if item.unit_cost_snapshot is not None else p.cost_price

                t_item = StockTransactionItem(
                    id=uuid.uuid4(),
                    business_id=current_user.business_id,
                    transaction_id=new_trx.id,
                    product_id=p.id,
                    quantity=item.quantity,
                    unit_cost_snapshot=unit_cost,
                    created_at=trx_at
                )
                db.add(t_item)

                if trx_type == "STOCK_IN":
                    p.current_stock += item.quantity
                else:
                    p.current_stock -= item.quantity

            db.commit()
            synced_trx_ids.append(trx_id)
        except Exception as e:
            db.rollback()
            failed_items.append({
                "type": "transaction",
                "id": str(trx_id),
                "reason": str(e)
            })

    return SyncPushResponse(
        synced_product_ids=synced_product_ids,
        synced_transaction_ids=synced_trx_ids,
        failed_items=failed_items,
        message=f"Berhasil menyinkronkan {len(synced_product_ids)} produk dan {len(synced_trx_ids)} transaksi."
    )

@router.get(
    "/pull",
    response_model=SyncPullResponse,
    summary="Tarik Data Terbaru dari Cloud (Pull)",
    description="Mengunduh data produk & transaksi terkini dari cloud untuk disimpan ke database lokal HP."
)
def sync_pull(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    products = db.query(Product).filter(
        Product.business_id == current_user.business_id,
        Product.status == "ACTIVE"
    ).all()

    recent_trx = db.query(StockTransaction).filter(
        StockTransaction.business_id == current_user.business_id
    ).order_by(StockTransaction.transaction_at.desc()).limit(100).all()

    return SyncPullResponse(
        server_time=datetime.now(timezone.utc),
        products=[ProductResponse.model_validate(p) for p in products],
        recent_transactions=[format_transaction_response(t) for t in recent_trx]
    )
