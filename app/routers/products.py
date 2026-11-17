import uuid
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse
from app.core.deps import get_current_user

router = APIRouter(prefix="/products", tags=["Master Produk (Products)"])

@router.get(
    "",
    response_model=ProductListResponse,
    summary="Daftar Produk & Pencarian",
    description="Mengambil daftar master produk untuk bisnis saat ini. Mendukung pencarian instan nama atau barcode (FR-09)."
)
def list_products(
    search: Optional[str] = Query(None, description="Kata kunci pencarian nama atau SKU/Barcode"),
    status: Optional[str] = Query("ACTIVE", description="Filter status: ACTIVE, ARCHIVED, atau ALL"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Product).filter(Product.business_id == current_user.business_id)

    # Filter status
    if status and status.upper() != "ALL":
        query = query.filter(Product.status == status.upper())

    # Pencarian case-insensitive (FR-09)
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_filter),
                Product.sku_barcode.ilike(search_filter)
            )
        )

    total = query.count()
    items = query.order_by(Product.name.asc()).offset(skip).limit(limit).all()

    return ProductListResponse(
        total=total,
        items=[ProductResponse.model_validate(p) for p in items]
    )

@router.get(
    "/barcode/{sku_barcode}",
    response_model=ProductResponse,
    summary="Cari Produk via Pemindaian Barcode Kamera",
    description="Mencari produk aktif berdasarkan kode barcode/SKU unik dalam satu bisnis (FR-06, FR-11)."
)
def get_by_barcode(
    sku_barcode: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(
        Product.business_id == current_user.business_id,
        Product.sku_barcode == sku_barcode.strip(),
        Product.status == "ACTIVE"
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produk dengan barcode '{sku_barcode}' tidak ditemukan atau berstatus diarsipkan."
        )

    return ProductResponse.model_validate(product)

@router.get(
    "/{id}",
    response_model=ProductResponse,
    summary="Detail Produk",
    description="Mengambil data detail produk berdasarkan ID."
)
def get_product(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(
        Product.id == id,
        Product.business_id == current_user.business_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produk tidak ditemukan."
        )

    return ProductResponse.model_validate(product)

@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tambah Produk Baru",
    description="Menambahkan master data produk baru. Mencegah duplikasi barcode dalam bisnis yang sama (FR-04, FR-07)."
)
def create_product(
    req: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validasi barcode duplikat dalam satu toko (FR-07 & Aturan Bisnis #3)
    if req.sku_barcode and req.sku_barcode.strip():
        barcode_clean = req.sku_barcode.strip()
        existing = db.query(Product).filter(
            Product.business_id == current_user.business_id,
            Product.sku_barcode == barcode_clean,
            Product.status == "ACTIVE"
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Barcode '{barcode_clean}' sudah digunakan oleh produk aktif '{existing.name}'."
            )
    else:
        barcode_clean = None

    # Idempotent check: jika ID client sudah ada
    product_id = req.id if req.id else uuid.uuid4()
    existing_id = db.query(Product).filter(Product.id == product_id).first()
    if existing_id:
        return ProductResponse.model_validate(existing_id)

    new_product = Product(
        id=product_id,
        business_id=current_user.business_id,
        sku_barcode=barcode_clean,
        name=req.name.strip(),
        unit=req.unit.strip(),
        cost_price=req.cost_price,
        selling_price=req.selling_price,
        current_stock=req.current_stock,
        status="ACTIVE",
        sync_status="SYNCED"
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return ProductResponse.model_validate(new_product)

@router.put(
    "/{id}",
    response_model=ProductResponse,
    summary="Ubah Informasi Produk",
    description="Memperbarui nama, unit, harga, atau barcode produk (FR-08)."
)
def update_product(
    id: UUID,
    req: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(
        Product.id == id,
        Product.business_id == current_user.business_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produk tidak ditemukan."
        )

    # Validasi duplikasi barcode jika diubah
    if req.sku_barcode is not None:
        barcode_clean = req.sku_barcode.strip() if req.sku_barcode.strip() else None
        if barcode_clean and barcode_clean != product.sku_barcode:
            duplicate = db.query(Product).filter(
                Product.business_id == current_user.business_id,
                Product.sku_barcode == barcode_clean,
                Product.status == "ACTIVE",
                Product.id != id
            ).first()
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Barcode '{barcode_clean}' sudah digunakan oleh produk '{duplicate.name}'."
                )
        product.sku_barcode = barcode_clean

    if req.name is not None:
        product.name = req.name.strip()
    if req.unit is not None:
        product.unit = req.unit.strip()
    if req.cost_price is not None:
        product.cost_price = req.cost_price
    if req.selling_price is not None:
        product.selling_price = req.selling_price
    if req.status is not None:
        product.status = req.status.upper()

    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)

@router.delete(
    "/{id}",
    response_model=ProductResponse,
    summary="Arsipkan Produk (Soft Delete)",
    description="Mengubah status produk menjadi ARCHIVED sesuai Aturan Bisnis #2 agar integritas riwayat transaksi tetap terjaga."
)
def archive_product(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(
        Product.id == id,
        Product.business_id == current_user.business_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produk tidak ditemukan."
        )

    product.status = "ARCHIVED"
    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)
