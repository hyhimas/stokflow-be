const { v4: uuidv4 } = require('uuid');
const prisma = require('../config/prisma');

const generateTransactionNumber = async (tx, businessId, businessCode) => {
  const currentYear = new Date().getFullYear();
  const startOfYear = new Date(currentYear, 0, 1);
  const endOfYear = new Date(currentYear, 11, 31, 23, 59, 59, 999);

  // Hitung jumlah transaksi tahun ini untuk bisnis ini
  const count = await tx.stockTransaction.count({
    where: {
      businessId,
      createdAt: {
        gte: startOfYear,
        lte: endOfYear,
      },
    },
  });

  const nextNumber = String(count + 1).padStart(6, '0');
  return `${businessCode}-${currentYear}-${nextNumber}`;
};

const getTransactions = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const {
      search,
      type,
      start_date,
      end_date,
      product_id,
      sort_by,
      sort_order,
      page,
      limit,
    } = req.validatedQuery;

    const where = {
      businessId,
    };

    // 1. Filter Type
    if (type) {
      where.type = type;
    }

    // 2. Filter Date Range
    if (start_date || end_date) {
      where.transactionAt = {};
      if (start_date) {
        where.transactionAt.gte = new Date(start_date);
      }
      if (end_date) {
        const endDateObj = new Date(end_date);
        // Jika hanya YYYY-MM-DD, set ke akhir hari
        if (end_date.length === 10) {
          endDateObj.setHours(23, 59, 59, 999);
        }
        where.transactionAt.lte = endDateObj;
      }
    }

    // 3. Filter by Product ID
    if (product_id) {
      where.items = {
        some: {
          productId: product_id,
        },
      };
    }

    // 4. Search on transactionNumber, notes, or product name
    if (search && search.trim() !== '') {
      const cleanSearch = search.trim();
      where.OR = [
        { transactionNumber: { contains: cleanSearch, mode: 'insensitive' } },
        { notes: { contains: cleanSearch, mode: 'insensitive' } },
        {
          items: {
            some: {
              product: {
                name: { contains: cleanSearch, mode: 'insensitive' },
              },
            },
          },
        },
      ];
    }

    // 5. Sorting
    const sortFieldMap = {
      transaction_at: 'transactionAt',
      created_at: 'createdAt',
      transaction_number: 'transactionNumber',
    };
    const orderByField = sortFieldMap[sort_by] || 'transactionAt';
    const orderByDirection = sort_order.toLowerCase() === 'asc' ? 'asc' : 'desc';

    // 6. Pagination
    const skip = (page - 1) * limit;

    const [total, transactions] = await Promise.all([
      prisma.stockTransaction.count({ where }),
      prisma.stockTransaction.findMany({
        where,
        orderBy: { [orderByField]: orderByDirection },
        skip,
        take: limit,
        include: {
          creator: {
            select: {
              id: true,
              name: true,
            },
          },
          items: {
            include: {
              product: {
                select: {
                  id: true,
                  name: true,
                  skuBarcode: true,
                  unit: true,
                },
              },
            },
          },
        },
      }),
    ]);

    const totalPages = Math.ceil(total / limit) || 1;

    return res.status(200).json({
      success: true,
      data: transactions,
      meta: {
        total,
        page,
        limit,
        total_pages: totalPages,
      },
    });
  } catch (error) {
    next(error);
  }
};

const getTransactionById = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const { id } = req.params;

    const transaction = await prisma.stockTransaction.findFirst({
      where: {
        id,
        businessId,
      },
      include: {
        creator: {
          select: {
            id: true,
            name: true,
            email: true,
            phone: true,
          },
        },
        items: {
          include: {
            product: {
              select: {
                id: true,
                name: true,
                skuBarcode: true,
                unit: true,
                costPrice: true,
                sellingPrice: true,
                currentStock: true,
              },
            },
          },
        },
      },
    });

    if (!transaction) {
      return res.status(404).json({
        success: false,
        message: 'Transaksi tidak ditemukan.',
        errors: [`Transaction with id ${id} not found`],
      });
    }

    const totalQuantity = transaction.items.reduce((sum, item) => sum + item.quantity, 0);

    return res.status(200).json({
      success: true,
      data: {
        ...transaction,
        total_items_count: transaction.items.length,
        total_quantity: totalQuantity,
      },
    });
  } catch (error) {
    next(error);
  }
};

const createTransaction = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const userId = req.user.id;
    const {
      id,
      transaction_number,
      type,
      notes,
      transaction_at,
      items,
    } = req.body;

    const transactionId = id || uuidv4();

    // Idempotent check: jika id transaksi sudah ada, langsung kembalikan transaksi lama
    const existingTransaction = await prisma.stockTransaction.findUnique({
      where: { id: transactionId },
      include: {
        creator: { select: { id: true, name: true } },
        items: {
          include: {
            product: {
              select: { id: true, name: true, skuBarcode: true, unit: true },
            },
          },
        },
      },
    });

    if (existingTransaction) {
      return res.status(200).json({
        success: true,
        message: 'Transaksi sudah pernah tersimpan (idempotent).',
        data: existingTransaction,
      });
    }

    // Jalankan transaksi atomik ACID
    const result = await prisma.$transaction(async (tx) => {
      // 1. Ambil data bisnis untuk prefix kode transaksi
      const business = await tx.business.findUnique({
        where: { id: businessId },
        select: { code: true },
      });

      const txNumber =
        transaction_number && transaction_number.trim() !== ''
          ? transaction_number.trim()
          : await generateTransactionNumber(tx, businessId, business.code);

      // Cek apakah nomor transaksi sudah ada
      const existingTxNumber = await tx.stockTransaction.findFirst({
        where: {
          businessId,
          transactionNumber: txNumber,
        },
      });

      if (existingTxNumber) {
        throw {
          statusCode: 409,
          message: `Nomor transaksi '${txNumber}' sudah pernah digunakan.`,
        };
      }

      // 2. Kumpulkan semua produk dan validasi kepemilikan bisnis
      const productIds = items.map((i) => i.product_id);
      const products = await tx.product.findMany({
        where: {
          id: { in: productIds },
          businessId,
        },
      });

      if (products.length !== productIds.length) {
        const foundIds = new Set(products.map((p) => p.id));
        const missingIds = productIds.filter((pId) => !foundIds.has(pId));
        throw {
          statusCode: 404,
          message: 'Satu atau lebih produk tidak ditemukan dalam bisnis Anda.',
          errors: missingIds.map((mId) => `Product ID ${mId} not found in this business`),
        };
      }

      const productMap = new Map(products.map((p) => [p.id, p]));

      // 3. FR-14: Validasi stok minus jika type === STOCK_OUT
      if (type === 'STOCK_OUT') {
        const insufficientProducts = [];
        for (const item of items) {
          const prod = productMap.get(item.product_id);
          if (prod.currentStock < item.quantity) {
            insufficientProducts.push({
              product_id: prod.id,
              name: prod.name,
              available_stock: prod.currentStock,
              requested_quantity: item.quantity,
              unit: prod.unit,
            });
          }
        }

        if (insufficientProducts.length > 0) {
          const details = insufficientProducts
            .map(
              (p) =>
                `'${p.name}' (stok tersedia: ${p.available_stock} ${p.unit}, diminta keluar: ${p.requested_quantity} ${p.unit})`
            )
            .join('; ');

          throw {
            statusCode: 400,
            message: `Stok tidak mencukupi untuk melakukan transaksi keluar: ${details}. Aturan bisnis: Stok tidak boleh bernilai minus.`,
            errors: insufficientProducts,
          };
        }
      }

      // 4. Buat Header Transaksi
      const transactionRecord = await tx.stockTransaction.create({
        data: {
          id: transactionId,
          businessId,
          transactionNumber: txNumber,
          type,
          notes: notes ? notes.trim() : null,
          createdBy: userId,
          transactionAt: transaction_at ? new Date(transaction_at) : new Date(),
        },
      });

      // 5. Buat Items dan Update currentStock setiap produk
      const createdItems = [];
      for (const item of items) {
        const prod = productMap.get(item.product_id);
        const itemId = item.id || uuidv4();

        const txItem = await tx.stockTransactionItem.create({
          data: {
            id: itemId,
            businessId,
            transactionId: transactionRecord.id,
            productId: prod.id,
            quantity: item.quantity,
            unitCostSnapshot: prod.costPrice,
            createdAt: transactionRecord.transactionAt,
          },
          include: {
            product: {
              select: {
                id: true,
                name: true,
                skuBarcode: true,
                unit: true,
              },
            },
          },
        });
        createdItems.push(txItem);

        // Update currentStock
        const stockDelta = type === 'STOCK_IN' ? item.quantity : -item.quantity;
        await tx.product.update({
          where: { id: prod.id },
          data: {
            currentStock: {
              increment: stockDelta,
            },
          },
        });
      }

      return {
        ...transactionRecord,
        items: createdItems,
      };
    });

    return res.status(201).json({
      success: true,
      message: `Transaksi ${type === 'STOCK_IN' ? 'Barang Masuk' : 'Barang Keluar'} berhasil dicatat.`,
      data: result,
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getTransactions,
  getTransactionById,
  createTransaction,
};
