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
    summary="Daftar Produk, Pencarian & Filter",
    description="Mengambil daftar master produk dengan filter lengkap (status, stok, satuan), pencarian nama/barcode, serta pengurutan ASC/DESC (FR-09, FR-10)."
)
def list_products(
    search: Optional[str] = Query(None, description="Pencarian kata kunci nama produk atau kode barcode/SKU"),
    status: Optional[str] = Query("ACTIVE", description="Filter status: ACTIVE, ARCHIVED, atau ALL"),
    unit: Optional[str] = Query(None, description="Filter satuan produk (contoh: pcs, dus, kg, pack)"),
    min_stock: Optional[int] = Query(None, ge=0, description="Filter stok minimal"),
    max_stock: Optional[int] = Query(None, ge=0, description="Filter stok maksimal (contoh: 0 untuk stok habis)"),
    sort_by: Optional[str] = Query("name", description="Urutkan berdasarkan: name, current_stock, selling_price, cost_price, created_at"),
    order: Optional[str] = Query("asc", description="Arah pengurutan: asc (A-Z / terkecil) atau desc (Z-A / terbesar)"),
    page: int = Query(1, ge=1, description="Nomor halaman (mulai dari 1)"),
    size: int = Query(20, ge=1, le=100, description="Jumlah barang per halaman (default: 20, max: 100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Product).filter(Product.business_id == current_user.business_id)

    # 1. Filter Status
    if status and status.upper() != "ALL":
        query = query.filter(Product.status == status.upper())

    # 2. Filter Satuan (Unit)
    if unit and unit.strip():
        query = query.filter(Product.unit.ilike(unit.strip()))

    # 3. Filter Rentang Stok
    if min_stock is not None:
        query = query.filter(Product.current_stock >= min_stock)
    if max_stock is not None:
        query = query.filter(Product.current_stock <= max_stock)

    # 4. Pencarian Case-Insensitive (Nama atau Barcode)
    if search and search.strip():
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_filter),
                Product.sku_barcode.ilike(search_filter)
            )
        )

    # 5. Sorting (Ascending / Descending)
    sort_column_map = {
        "name": Product.name,
        "current_stock": Product.current_stock,
        "selling_price": Product.selling_price,
        "cost_price": Product.cost_price,
        "created_at": Product.created_at,
    }
    sort_column = sort_column_map.get(sort_by.lower() if sort_by else "name", Product.name)
    if order and order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 6. Pagination
    total = query.count()
    offset = (page - 1) * size
    total_pages = (total + size - 1) // size if total > 0 else 1

    items = query.offset(offset).limit(size).all()

    return ProductListResponse(
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
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
