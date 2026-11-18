const { z } = require('zod');

const syncPushSchema = z.object({
  products: z
    .array(
      z.object({
        id: z.string().uuid('Format ID produk harus berupa UUID v4'),
        sku_barcode: z.string().max(100).optional().nullable(),
        name: z.string().min(1, 'Nama produk wajib diisi').max(255),
        unit: z.string().min(1).default('pcs'),
        cost_price: z.coerce.number().min(0).default(0),
        selling_price: z.coerce.number().min(0).default(0),
        current_stock: z.coerce.number().int().min(0).default(0),
        status: z.enum(['ACTIVE', 'ARCHIVED']).default('ACTIVE'),
      })
    )
    .default([]),
  transactions: z
    .array(
      z.object({
        id: z.string().uuid('Format ID transaksi harus berupa UUID v4'),
        transaction_number: z.string().optional(),
        type: z.enum(['STOCK_IN', 'STOCK_OUT']),
        notes: z.string().max(1000).optional().nullable(),
        transaction_at: z
          .string()
          .refine((val) => !isNaN(Date.parse(val)), { message: 'Format tanggal transaction_at tidak valid' })
          .optional(),
        items: z
          .array(
            z.object({
              id: z.string().uuid().optional(),
              product_id: z.string().uuid('Format product_id harus berupa UUID v4'),
              quantity: z.coerce.number().int().min(1),
            })
          )
          .min(1, 'Transaksi minimal harus memiliki 1 item barang'),
      })
    )
    .default([]),
});

const syncPullQuerySchema = z.object({
  last_synced_at: z
    .string()
    .refine((val) => !isNaN(Date.parse(val)), { message: 'Format last_synced_at tidak valid' })
    .optional(),
});

module.exports = {
  syncPushSchema,
  syncPullQuerySchema,
};
