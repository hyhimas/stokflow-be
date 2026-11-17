from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.routers.auth import router as auth_router
from app.routers.products import router as products_router
from app.routers.transactions import router as transactions_router
from app.routers.sync import router as sync_router

app = FastAPI(
    title="STOKFLOW API - Inventaris UMKM",
    description="""
# STOKFLOW REST API (Fase 1 - MVP)
Platform Inventaris & Pengelolaan Stok UMKM Multi-Business berbasis Offline-First.

### Spesifikasi Teknis:
* **Model SaaS**: Multi-Business dengan isolasi ketat `business_id` (Shared Database, Shared Schema).
* **Autentikasi**: JWT Bearer Token.
* **Master Produk**: Pencatatan barang, harga modal & jual, stok awal, serta pemindaian barcode unik per toko.
* **Transaksi Stok**: `STOCK_IN` (penambahan) & `STOCK_OUT` (pengurangan dengan validasi stok minus).
* **Offline-First**: Sinkronisasi push & pull data lokal SQLite/Drift ke Neon PostgreSQL Cloud.

---
*Gunakan tombol **Authorize** di bawah untuk memasukkan token JWT setelah melakukan registrasi atau login.*
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware (mengizinkan akses dari aplikasi Flutter di emulator/perangkat fisik)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers dengan prefix /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")

@app.get("/", tags=["Health Check"])
def root():
    return {
        "status": "online",
        "app": "STOKFLOW API",
        "version": "1.0.0",
        "documentation": "/docs"
    }

@app.get("/health", tags=["Health Check"])
def health_check():
    return {
        "status": "ok",
        "database": "Neon Serverless PostgreSQL (Connected)",
        "offline_sync": "ready"
    }

# Konfigurasi custom OpenAPI schema untuk Swagger Authorize dialog
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Masukkan access_token yang didapat dari endpoint /api/v1/auth/login atau /api/v1/auth/register"
        }
    }
    # Terapkan security scheme secara global
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
