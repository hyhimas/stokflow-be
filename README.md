# StokFlow UMKM Backend REST API

Production-ready Backend REST API untuk aplikasi mobile **StokFlow UMKM (MVP)** menggunakan **Node.js, Express.js, Prisma ORM, PostgreSQL (Neon Serverless)**, dan **Swagger UI (`openapi.yaml`)**, siap di-deploy ke **Vercel Serverless**.

---

## 🛠️ Tech Stack & Fitur Utama
- **Runtime & Framework:** Node.js, Express.js (`cors`, `helmet`, `dotenv`).
- **Database & ORM:** PostgreSQL di Neon Serverless dengan Prisma ORM.
  - Koneksi Singleton `global.prisma` (aman dari kebocoran koneksi saat Vercel cold-start).
  - Skema Multi-Business SaaS (Shared Database, Shared Schema) dengan isolasi ketat `business_id`.
  - Dukungan UUID v4 dari klien Flutter untuk arsitektur **Offline-First & Idempotent Sync**.
- **Keamanan & Validasi:**
  - `jsonwebtoken` (JWT Bearer Token dengan masa aktif 7 hari).
  - `bcryptjs` untuk hashing password.
  - `zod` untuk validasi menyeluruh pada request body, query params, dan path params.
- **Dokumentasi API:**
  - Swagger UI interaktif di endpoint `/api-docs` (menggunakan `swagger-ui-express` + `yamljs`).
  - Dilengkapi Cloudflare CDN CSS & JS serta `persistAuthorization: true` agar tidak terjadi *blank screen* saat di-deploy ke Vercel.

---

## 📂 Struktur Proyek
```
d:\BE mobile\
├── .env                       # Variabel lingkungan (DATABASE_URL, DIRECT_URL, JWT_SECRET)
├── .env.example               # Contoh template variabel lingkungan
├── .gitignore                 # Daftar file terabaikan git
├── package.json               # Konfigurasi dependensi dan postinstall prisma generate
├── vercel.json                # Konfigurasi serverless Vercel (@vercel/node)
├── openapi.yaml               # Spesifikasi lengkap OpenAPI 3.0 / Swagger UI
├── prisma/
│   └── schema.prisma          # Skema database Prisma (Neon PostgreSQL)
└── src/
    ├── index.js               # Entry point aplikasi Express
    ├── config/
    │   └── prisma.js          # Singleton PrismaClient instance
    ├── middlewares/
    │   ├── auth.js            # authenticateJWT & authorizeRoles (RBAC)
    │   ├── errorHandler.js    # Global error handler (Zod, Prisma P2002/P2025)
    │   └── validate.js        # Helper validasi Zod (body, query, params)
    ├── validators/
    │   ├── authValidator.js
    │   ├── productValidator.js
    │   ├── transactionValidator.js
    │   └── syncValidator.js
    ├── controllers/
    │   ├── authController.js
    │   ├── productController.js
    │   ├── transactionController.js
    │   └── syncController.js
    └── routes/
        ├── authRoutes.js
        ├── productRoutes.js
        ├── transactionRoutes.js
        └── syncRoutes.js
```

---

## 🚀 Panduan Menjalankan Secara Lokal

1. **Install Dependensi & Generate Prisma Client:**
   ```bash
   npm install
   ```

2. **Sinkronisasi Skema Database ke Neon:**
   ```bash
   npx prisma db push
   ```

3. **Jalankan Server Lokal:**
   ```bash
   npm start
   # atau node src/index.js
   ```

4. **Akses Dokumentasi API:**
   - **Swagger UI:** [http://localhost:8000/api-docs](http://localhost:8000/api-docs)
   - **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🌐 Panduan Deploy ke Vercel Serverless

1. Push seluruh kode ke repository GitHub Anda:
   ```bash
   git add .
   git commit -m "feat: complete production-ready Node.js Express Prisma backend"
   git push origin main
   ```

2. Buka dashboard Vercel di [vercel.com](https://vercel.com):
   - Di tab **Settings** -> **Environment Variables**, pastikan variabel berikut terpasang:
     - `DATABASE_URL`: `postgresql://neondb_owner:password@ep-rough-pine-...-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
     - `DIRECT_URL`: `postgresql://neondb_owner:password@ep-rough-pine-...-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
     - `JWT_SECRET`: Kunci rahasia token JWT Anda
     - `JWT_EXPIRES_IN`: `7d`
     - `NODE_ENV`: `production`

3. URL Swagger publik Vercel Anda:
   `https://NAMA-PROJECT-ANDA.vercel.app/api-docs`

---

## 📡 Daftar Endpoint Lengkap (FR-01 s.d. FR-22)

### 1. Autentikasi (`/api/auth`)
- `POST /api/auth/register` — Registrasi pemilik usaha baru + toko baru (role OWNER).
- `POST /api/auth/login` — Login via email/phone + password.
- `GET /api/auth/me` — Info profil, toko, dan statistik ringkasan produk.
- `POST /api/auth/logout` — Logout sesi.

### 2. Master Produk (`/api/products`)
- `GET /api/products` — List produk dengan filter status, unit, stok, barcode scanner (`?barcode=...`), pencarian nama/sku, sorting asc/desc, pagination.
- `GET /api/products/:id` — Detail produk beserta 10 mutasi stok terakhir.
- `POST /api/products` — Tambah produk baru (validasi unik barcode per toko).
- `PUT /api/products/:id` — Edit informasi produk.
- `PATCH /api/products/:id/archive` — Arsipkan produk (soft delete).

### 3. Transaksi Stok (`/api/transactions`)
- `GET /api/transactions` — Riwayat transaksi dengan filter tipe (STOCK_IN/STOCK_OUT), rentang tanggal, produk, dan pencarian.
- `GET /api/transactions/:id` — Detail transaksi beserta rincian item barang dan pencatat.
- `POST /api/transactions` — Catat transaksi atomik ACID, auto-numbering, dan validasi anti-stok minus.

### 4. Offline-First Sync Engine (`/api/sync`)
- `GET /api/sync/pull` — Unduh perubahan data cloud terbaru untuk database lokal HP.
- `POST /api/sync/push` — Unggah antrean data offline berstatus PENDING secara idempotent dan terisolasi.
