const { z } = require('zod');

const createTransactionSchema = z.object({
  id: z.string().uuid('Format ID harus berupa UUID v4').optional(),
  transaction_number: z.string().max(50).optional(),
  type: z.enum(['STOCK_IN', 'STOCK_OUT'], {
    errorMap: () => ({ message: "Tipe transaksi harus 'STOCK_IN' atau 'STOCK_OUT'" }),
  }),
  notes: z.string().max(1000, 'Catatan maksimal 1000 karakter').optional().nullable(),
  transaction_at: z
    .string()
    .refine((val) => !isNaN(Date.parse(val)), { message: 'Format tanggal transaction_at tidak valid' })
    .optional(),
  items: z
    .array(
      z.object({
        id: z.string().uuid('Format item id harus berupa UUID v4').optional(),
        product_id: z.string().uuid('Format product_id harus berupa UUID v4'),
        quantity: z.coerce.number().int().min(1, 'Jumlah barang (quantity) harus minimal 1'),
      })
    )
    .min(1, 'Minimal harus menyertakan 1 item barang dalam transaksi'),
});

const getTransactionsQuerySchema = z.object({
  search: z.string().optional(),
  type: z.enum(['STOCK_IN', 'STOCK_OUT']).optional(),
  start_date: z
    .string()
    .refine((val) => !isNaN(Date.parse(val)), { message: 'Format start_date tidak valid (gunakan YYYY-MM-DD)' })
    .optional(),
  end_date: z
    .string()
    .refine((val) => !isNaN(Date.parse(val)), { message: 'Format end_date tidak valid (gunakan YYYY-MM-DD)' })
    .optional(),
  product_id: z.string().uuid('Format product_id harus UUID').optional(),
  sort_by: z.enum(['transaction_at', 'created_at', 'transaction_number']).default('transaction_at'),
  sort_order: z.enum(['asc', 'desc']).default('desc'),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(10),
});

module.exports = {
  createTransactionSchema,
  getTransactionsQuerySchema,
};
