require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const path = require('path');
const YAML = require('yamljs');
const swaggerUi = require('swagger-ui-express');

const prisma = require('./config/prisma');
const errorHandler = require('./middlewares/errorHandler');

const authRoutes = require('./routes/authRoutes');
const productRoutes = require('./routes/productRoutes');
const transactionRoutes = require('./routes/transactionRoutes');
const syncRoutes = require('./routes/syncRoutes');

const app = express();

// 1. Security & Core Middlewares
app.use(
  helmet({
    contentSecurityPolicy: false, // Nonaktifkan CSP agar Swagger UI CDN Cloudflare dapat dimuat tanpa error
  })
);
app.use(
  cors({
    origin: '*',
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
  })
);
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// 2. Swagger UI Setup dengan Cloudflare CDN Assets (Mencegah Blank Screen di Vercel)
const swaggerDocumentPath = path.join(process.cwd(), 'openapi.yaml');
let swaggerDocument = {};
try {
  swaggerDocument = YAML.load(swaggerDocumentPath);
} catch (err) {
  console.error('[Swagger] Gagal memuat openapi.yaml:', err);
}

const swaggerUiOptions = {
  customCssUrl: 'https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css',
  customJs: [
    'https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-standalone-preset.min.js',
  ],
  customSiteTitle: 'StokFlow UMKM - Swagger API Docs',
  swaggerOptions: {
    persistAuthorization: true,
    displayRequestDuration: true,
  },
};

app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerDocument, swaggerUiOptions));

// 3. Root Endpoint: Otomatis redirect ke /api-docs
app.get('/', (req, res) => {
  res.redirect('/api-docs');
});

// 4. Health Check Endpoint
app.get('/health', async (req, res) => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    res.status(200).json({
      success: true,
      message: 'StokFlow API is running smoothly',
      database: 'connected (Neon PostgreSQL)',
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    res.status(503).json({
      success: false,
      message: 'Database connection failed',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
  }
});

// 5. Mount API Routes
app.use('/api/auth', authRoutes);
app.use('/api/products', productRoutes);
app.use('/api/transactions', transactionRoutes);
app.use('/api/sync', syncRoutes);

// 6. 404 Handler untuk route yang tidak terdaftar
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: `Rute '${req.method} ${req.originalUrl}' tidak ditemukan. Silakan cek dokumentasi di /api-docs`,
    errors: ['Route not found'],
  });
});

// 7. Global Error Handler Middleware
app.use(errorHandler);

// 8. Server Listen (Hanya jika dijalankan langsung / bukan serverless Vercel)
const PORT = process.env.PORT || 8000;
if (process.env.NODE_ENV !== 'production' || !process.env.VERCEL) {
  app.listen(PORT, () => {
    console.log(`=======================================================`);
    console.log(`  StokFlow UMKM Backend API Server running on port ${PORT}`);
    console.log(`  Swagger UI Docs: http://localhost:${PORT}/api-docs`);
    console.log(`  Health Check   : http://localhost:${PORT}/health`);
    console.log(`=======================================================`);
  });
}

module.exports = app;
