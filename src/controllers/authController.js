const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const prisma = require('../config/prisma');

const generateToken = (payload) => {
  const secret = process.env.JWT_SECRET || 'stokflow-super-secret-production-key-2026';
  const expiresIn = process.env.JWT_EXPIRES_IN || '7d';
  return jwt.sign(payload, secret, { expiresIn });
};

const register = async (req, res, next) => {
  try {
    const {
      name,
      email,
      phone,
      password,
      business_name,
      business_code,
      business_type,
      address,
    } = req.body;

    const normalizedCode = business_code.trim().toUpperCase();
    const cleanEmail = email && email.trim() !== '' ? email.trim().toLowerCase() : null;
    const cleanPhone = phone && phone.trim() !== '' ? phone.trim() : null;

    // 1. Cek duplikasi kode bisnis
    const existingBusiness = await prisma.business.findUnique({
      where: { code: normalizedCode },
    });

    if (existingBusiness) {
      return res.status(409).json({
        success: false,
        message: `Kode toko/bisnis '${normalizedCode}' sudah digunakan. Silakan gunakan kode lain.`,
        errors: ['business_code must be unique'],
      });
    }

    // 2. Cek duplikasi email jika diisi
    if (cleanEmail) {
      const existingEmail = await prisma.user.findUnique({
        where: { email: cleanEmail },
      });
      if (existingEmail) {
        return res.status(409).json({
          success: false,
          message: 'Email sudah terdaftar. Silakan login atau gunakan email lain.',
          errors: ['Email already exists'],
        });
      }
    }

    // 3. Cek duplikasi phone jika diisi
    if (cleanPhone) {
      const existingPhone = await prisma.user.findUnique({
        where: { phone: cleanPhone },
      });
      if (existingPhone) {
        return res.status(409).json({
          success: false,
          message: 'Nomor HP sudah terdaftar. Silakan login atau gunakan nomor lain.',
          errors: ['Phone already exists'],
        });
      }
    }

    // 4. Hash password
    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(password, salt);

    // 5. Jalankan transaksi atomik Prisma
    const result = await prisma.$transaction(async (tx) => {
      const business = await tx.business.create({
        data: {
          code: normalizedCode,
          name: business_name.trim(),
          businessType: business_type ? business_type.trim() : null,
          address: address ? address.trim() : null,
          status: 'ACTIVE',
        },
      });

      const user = await tx.user.create({
        data: {
          businessId: business.id,
          name: name.trim(),
          email: cleanEmail,
          phone: cleanPhone,
          passwordHash,
          role: 'OWNER',
          status: 'ACTIVE',
          lastLoginAt: new Date(),
        },
      });

      return { business, user };
    });

    // 6. Buat JWT
    const token = generateToken({
      userId: result.user.id,
      businessId: result.business.id,
      role: result.user.role,
      name: result.user.name,
      email: result.user.email,
    });

    return res.status(201).json({
      success: true,
      message: 'Registrasi pemilik usaha dan profil bisnis berhasil.',
      data: {
        token,
        user: {
          id: result.user.id,
          name: result.user.name,
          email: result.user.email,
          phone: result.user.phone,
          role: result.user.role,
          status: result.user.status,
          created_at: result.user.createdAt,
        },
        business: {
          id: result.business.id,
          code: result.business.code,
          name: result.business.name,
          business_type: result.business.businessType,
          address: result.business.address,
          status: result.business.status,
          created_at: result.business.createdAt,
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

const login = async (req, res, next) => {
  try {
    const { identifier, password } = req.body;
    const cleanIdentifier = identifier.trim();

    // Cari user berdasarkan email atau nomor HP
    const user = await prisma.user.findFirst({
      where: {
        OR: [
          { email: cleanIdentifier.toLowerCase() },
          { phone: cleanIdentifier },
        ],
      },
      include: {
        business: true,
      },
    });

    if (!user) {
      return res.status(401).json({
        success: false,
        message: 'Kredensial tidak valid. Email/Nomor HP atau kata sandi salah.',
        errors: ['Invalid credentials'],
      });
    }

    // Validasi password
    const isPasswordValid = await bcrypt.compare(password, user.passwordHash);
    if (!isPasswordValid) {
      return res.status(401).json({
        success: false,
        message: 'Kredensial tidak valid. Email/Nomor HP atau kata sandi salah.',
        errors: ['Invalid credentials'],
      });
    }

    // FR-03: Validasi status user dan bisnis
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

    // Update lastLoginAt
    await prisma.user.update({
      where: { id: user.id },
      data: { lastLoginAt: new Date() },
    });

    // Generate Token
    const token = generateToken({
      userId: user.id,
      businessId: user.business.id,
      role: user.role,
      name: user.name,
      email: user.email,
    });

    return res.status(200).json({
      success: true,
      message: 'Login berhasil.',
      data: {
        token,
        user: {
          id: user.id,
          name: user.name,
          email: user.email,
          phone: user.phone,
          role: user.role,
          status: user.status,
          last_login_at: new Date(),
        },
        business: {
          id: user.business.id,
          code: user.business.code,
          name: user.business.name,
          business_type: user.business.businessType,
          address: user.business.address,
          status: user.business.status,
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

const getMe = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;

    // Ambil data user, bisnis, serta ringkasan statistik
    const [user, stats] = await Promise.all([
      prisma.user.findUnique({
        where: { id: req.user.id },
        include: { business: true },
      }),
      prisma.product.aggregate({
        where: {
          businessId,
          status: 'ACTIVE',
        },
        _count: { id: true },
        _sum: { currentStock: true },
      }),
    ]);

    return res.status(200).json({
      success: true,
      data: {
        user: {
          id: user.id,
          name: user.name,
          email: user.email,
          phone: user.phone,
          role: user.role,
          status: user.status,
          last_login_at: user.lastLoginAt,
          created_at: user.createdAt,
        },
        business: {
          id: user.business.id,
          code: user.business.code,
          name: user.business.name,
          business_type: user.business.businessType,
          address: user.business.address,
          status: user.business.status,
          created_at: user.business.createdAt,
        },
        summary: {
          total_active_sku: stats._count.id || 0,
          total_stock_units: stats._sum.currentStock || 0,
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

const logout = async (req, res) => {
  return res.status(200).json({
    success: true,
    message: 'Logout berhasil. Hapus token dari penyimpanan lokal perangkat.',
  });
};

module.exports = {
  register,
  login,
  getMe,
  logout,
};
