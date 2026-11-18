const { ZodError } = require('zod');

const errorHandler = (err, req, res, next) => {
  console.error(`[Error] ${req.method} ${req.originalUrl}:`, err);

  // 1. Tangani Zod Validation Error (HTTP 400)
  if (err instanceof ZodError) {
    const errorDetails = err.errors.map((e) => {
      const field = e.path.join('.');
      return `${field ? field + ': ' : ''}${e.message}`;
    });

    return res.status(400).json({
      success: false,
      message: 'Validasi input gagal.',
      errors: errorDetails,
    });
  }

  // 2. Tangani Prisma Unique Constraint Violation (P2002 -> HTTP 409)
  if (err.code === 'P2002') {
    const target = err.meta && err.meta.target ? err.meta.target.join(', ') : 'field';
    return res.status(409).json({
      success: false,
      message: `Konflik data. Nilai pada ${target} sudah digunakan.`,
      errors: [`Unique constraint failed on field(s): ${target}`],
    });
  }

  // 3. Tangani Prisma Record Not Found (P2025 -> HTTP 404)
  if (err.code === 'P2025') {
    return res.status(404).json({
      success: false,
      message: 'Data yang diminta tidak ditemukan.',
      errors: [err.meta && err.meta.cause ? err.meta.cause : 'Record not found'],
    });
  }

  // 4. Tangani Prisma Foreign Key Constraint (P2003 -> HTTP 400)
  if (err.code === 'P2003') {
    const field = err.meta && err.meta.field_name ? err.meta.field_name : 'relasi';
    return res.status(400).json({
      success: false,
      message: 'Data relasi tidak valid atau tidak ditemukan.',
      errors: [`Foreign key constraint failed on: ${field}`],
    });
  }

  // 5. Tangani Custom HTTP Error jika ada status
  const statusCode = err.statusCode || err.status || 500;
  const message = err.message || 'Terjadi kesalahan internal pada server.';

  return res.status(statusCode).json({
    success: false,
    message,
    errors: process.env.NODE_ENV === 'development' ? [err.stack || err.toString()] : [message],
  });
};

module.exports = errorHandler;
