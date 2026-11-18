const jwt = require('jsonwebtoken');
const prisma = require('../config/prisma');

const authenticateJWT = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({
        success: false,
        message: 'Akses ditolak. Token otentikasi tidak ditemukan.',
        errors: ['Bearer token is required in Authorization header'],
      });
    }

    const token = authHeader.split(' ')[1];
    const secret = process.env.JWT_SECRET || 'stokflow-super-secret-production-key-2026';

    let decoded;
    try {
      decoded = jwt.verify(token, secret);
    } catch (err) {
      if (err.name === 'TokenExpiredError') {
        return res.status(401).json({
          success: false,
          message: 'Sesi telah kedaluwarsa. Silakan login kembali.',
          errors: ['Token has expired'],
        });
      }
      return res.status(401).json({
        success: false,
        message: 'Token otentikasi tidak valid.',
        errors: [err.message],
      });
    }

    const { userId, businessId } = decoded;

    // FR-03: Validasi status aktif User dan Business di database
    const user = await prisma.user.findUnique({
      where: { id: userId },
      include: { business: true },
    });

    if (!user) {
      return res.status(401).json({
        success: false,
        message: 'Pengguna tidak ditemukan dalam sistem.',
        errors: ['User not found'],
      });
    }

    if (user.status !== 'ACTIVE') {
      return res.status(403).json({
        success: false,
        message: 'Akun Anda dinonaktifkan. Silakan hubungi admin.',
        errors: [`User status is ${user.status}`],
      });
    }

    if (!user.business || user.business.status !== 'ACTIVE') {
      return res.status(403).json({
        success: false,
        message: 'Layanan bisnis toko Anda berstatus nonaktif atau ditangguhkan.',
        errors: [`Business status is ${user.business ? user.business.status : 'UNKNOWN'}`],
      });
    }

    // Set user context di req.user
    // Isolasi Multi-Business: backend selalu memakai req.user.businessId dari token/db terverifikasi
    req.user = {
      id: user.id,
      userId: user.id,
      businessId: user.businessId,
      name: user.name,
      email: user.email,
      phone: user.phone,
      role: user.role,
      business: user.business,
    };

    next();
  } catch (error) {
    next(error);
  }
};

const authorizeRoles = (...allowedRoles) => {
  return (req, res, next) => {
    if (!req.user || !allowedRoles.includes(req.user.role)) {
      return res.status(403).json({
        success: false,
        message: 'Akses terlarang. Anda tidak memiliki izin untuk tindakan ini.',
        errors: [`Required role: ${allowedRoles.join(' or ')}. Your role: ${req.user ? req.user.role : 'None'}`],
      });
    }
    next();
  };
};

module.exports = {
  authenticateJWT,
  authorizeRoles,
};
