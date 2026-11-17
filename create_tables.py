import os
import sys
from sqlalchemy import inspect
from app.database import engine, Base
from app.models import Business, User, Product, StockTransaction, StockTransactionItem

def create_all_tables():
    print("=" * 60)
    print("  MEMBUAT TABEL DATABASE NEON BERDASARKAN PRD BAB 13")
    print("=" * 60)

    try:
        print("\n[1/3] Menghubungkan ke Neon & mengeksekusi DDL pembuatan tabel...")
        Base.metadata.create_all(bind=engine)
        print("  -> Metadata schema berhasil dieksekusi!")

        print("\n[2/3] Memeriksa tabel yang terdaftar di database...")
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        expected_tables = [
            "businesses",
            "users",
            "products",
            "stock_transactions",
            "stock_transaction_items"
        ]

        print("\n[3/3] Verifikasi Hasil:")
        for tbl in expected_tables:
            if tbl in tables:
                cols = inspector.get_columns(tbl)
                col_names = [c["name"] for c in cols]
                print(f"  [OK] Tabel '{tbl}': {len(col_names)} kolom -> {', '.join(col_names)}")
            else:
                print(f"  [X] Tabel '{tbl}' TIDAK DITEMUKAN!")

        print("\n" + "=" * 60)
        print("  SEMUA TABEL MVP BERHASIL DIBUAT DI NEON POSTGRESQL!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Gagal membuat tabel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    create_all_tables()
