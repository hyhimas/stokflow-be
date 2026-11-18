const { z } = require('zod');

const registerSchema = z
  .object({
    name: z.string().min(2, 'Nama pengguna minimal 2 karakter').max(100),
    email: z.string().email('Format email tidak valid').optional().or(z.literal('')),
    phone: z
      .string()
      .min(8, 'Nomor HP minimal 8 digit')
      .max(20, 'Nomor HP maksimal 20 digit')
      .regex(/^[0-9+]+$/, 'Nomor HP hanya boleh berisi angka dan tanda plus (+)')
      .optional()
      .or(z.literal('')),
    password: z.string().min(6, 'Kata sandi minimal 6 karakter').max(100),
    business_name: z.string().min(2, 'Nama toko/bisnis minimal 2 karakter').max(150),
    business_code: z
      .string()
      .min(2, 'Kode bisnis minimal 2 karakter')
      .max(20, 'Kode bisnis maksimal 20 karakter')
      .regex(/^[A-Za-z0-9_-]+$/, 'Kode bisnis hanya boleh alfanumerik, dash (-), atau underscore (_)'),
    business_type: z.string().max(100).optional().or(z.literal('')),
    address: z.string().max(500).optional().or(z.literal('')),
  })
  .refine(
    (data) => (data.email && data.email.trim() !== '') || (data.phone && data.phone.trim() !== ''),
    {
      message: 'Wajib mengisi minimal salah satu dari Email atau Nomor HP.',
      path: ['email'],
    }
  );

const loginSchema = z.object({
  identifier: z.string().min(1, 'Email atau Nomor HP wajib diisi'),
  password: z.string().min(1, 'Kata sandi wajib diisi'),
});

module.exports = {
  registerSchema,
  loginSchema,
};
