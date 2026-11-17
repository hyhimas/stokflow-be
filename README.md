# STOKFLOW Backend (FastAPI + Neon PostgreSQL)

Backend REST API untuk aplikasi mobile inventaris UMKM (STOKFLOW) sesuai PRD MVP Fase 1.

## Tech Stack
- **Framework**: FastAPI (Python 3.10+)
- **Database**: Neon Serverless PostgreSQL
- **ORM / Driver**: SQLAlchemy 2.0 + pg8000 (Pure-Python Driver)
- **API Documentation**: OpenAPI / Swagger UI

## Struktur Direktori
```
d:\BE mobile\
├── .env                  # Konfigurasi DATABASE_URL Neon
├── requirements.txt      # Dependensi Python
├── create_tables.py      # Skrip DDL pembuat tabel Neon (PRD Bab 13)
├── app/
│   ├── database.py       # Engine SQLAlchemy & SessionLocal
│   ├── main.py           # Inisialisasi FastAPI & Swagger UI
│   └── models/           # Definisi tabel ORM
│       ├── business.py   # Tabel `businesses`
│       ├── user.py       # Tabel `users`
│       ├── product.py    # Tabel `products`
│       └── transaction.py# Tabel `stock_transactions` & `stock_transaction_items`
```

## Cara Menjalankan Backend

1. Install dependensi (jika belum):
   ```bash
   pip install -r requirements.txt
   ```

2. Buat / perbarui tabel database di Neon (sudah selesai dijalankan):
   ```bash
   python create_tables.py
   ```

3. Jalankan server lokal:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

4. Buka Swagger Documentation di browser:
   - **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
