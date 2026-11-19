const { z } = require('zod');

const createProductSchema = z.object({
  id: z.string().uuid('Format ID harus berupa UUID v4').optional(),
  sku_barcode: z.string().max(100, 'Barcode maksimal 100 karakter').optional().nullable(),
  name: z.string().min(1, 'Nama produk wajib diisi').max(255, 'Nama produk maksimal 255 karakter'),
  unit: z.string().min(1, 'Satuan produk wajib diisi').default('pcs'),
  cost_price: z.coerce.number().min(0, 'Harga modal tidak boleh bernilai negatif').default(0),
  selling_price: z.coerce.number().min(0, 'Harga jual tidak boleh bernilai negatif').default(0),
  current_stock: z.coerce.number().int().min(0, 'Stok awal tidak boleh bernilai negatif').default(0),
});

const updateProductSchema = z.object({
  sku_barcode: z.string().max(100, 'Barcode maksimal 100 karakter').optional().nullable(),
  name: z.string().min(1, 'Nama produk wajib diisi').max(255).optional(),
  unit: z.string().min(1, 'Satuan produk wajib diisi').optional(),
  cost_price: z.coerce.number().min(0, 'Harga modal tidak boleh bernilai negatif').optional(),
  selling_price: z.coerce.number().min(0, 'Harga jual tidak boleh bernilai negatif').optional(),
  current_stock: z.coerce.number().int().min(0, 'Stok tidak boleh bernilai negatif').optional(),
  status: z.enum(['ACTIVE', 'ARCHIVED']).optional(),
});

const getProductsQuerySchema = z.object({
  search: z.string().optional(),
  barcode: z.string().optional(),
  status: z.enum(['ACTIVE', 'ARCHIVED', 'ALL']).default('ACTIVE'),
  stock_status: z.enum(['AVAILABLE', 'EMPTY']).optional(),
  unit: z.string().optional(),
  sort_by: z
    .enum(['name', 'current_stock', 'selling_price', 'cost_price', 'updated_at', 'created_at'])
    .default('updated_at'),
  sort_order: z.enum(['asc', 'desc']).default('desc'),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(10),
});

module.exports = {
  createProductSchema,
  updateProductSchema,
  getProductsQuerySchema,
};
