const { v4: uuidv4 } = require('uuid');
const prisma = require('../config/prisma');

const pullSync = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const { last_synced_at } = req.query;

    const serverTime = new Date().toISOString();

    let productWhere = { businessId };
    let transactionWhere = { businessId };

    if (last_synced_at) {
      const sinceDate = new Date(last_synced_at);
      productWhere.updatedAt = { gte: sinceDate };
      transactionWhere.createdAt = { gte: sinceDate };
    }

    const [products, transactions] = await Promise.all([
      prisma.product.findMany({
        where: productWhere,
        orderBy: { updatedAt: 'desc' },
      }),
      prisma.stockTransaction.findMany({
        where: transactionWhere,
        orderBy: { transactionAt: 'desc' },
        take: last_synced_at ? undefined : 100, // Jika initial sync, batasi 100 transaksi terbaru
        include: {
          creator: {
            select: { id: true, name: true },
          },
          items: {
            include: {
              product: {
                select: { id: true, name: true, skuBarcode: true, unit: true },
              },
            },
          },
        },
      }),
    ]);

    return res.status(200).json({
      success: true,
      data: {
        server_time: serverTime,
        products,
        transactions,
      },
    });
  } catch (error) {
    next(error);
  }
};

const pushSync = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const userId = req.user.id;
    const { products = [], transactions = [] } = req.body;

    const syncedProductIds = [];
    const syncedTransactionIds = [];
    const failedItems = [];

    // 1. Proses Sinkronisasi Produk (Idempotent Upsert)
    for (const prod of products) {
      try {
        const cleanBarcode = prod.sku_barcode && prod.sku_barcode.trim() !== '' ? prod.sku_barcode.trim() : null;

        // Cek duplikasi barcode terhadap produk lain yang aktif
        if (cleanBarcode) {
          const duplicate = await prisma.product.findFirst({
            where: {
              businessId,
              skuBarcode: cleanBarcode,
              status: 'ACTIVE',
              NOT: { id: prod.id },
            },
          });

          if (duplicate) {
            failedItems.push({
              id: prod.id,
              entity: 'product',
              name: prod.name,
              reason: `Barcode '${cleanBarcode}' sudah digunakan oleh produk aktif '${duplicate.name}'`,
            });
            continue;
          }
        }

        // Upsert produk
        await prisma.product.upsert({
          where: { id: prod.id },
          create: {
            id: prod.id,
            businessId,
            skuBarcode: cleanBarcode,
            name: prod.name.trim(),
            unit: prod.unit ? prod.unit.trim() : 'pcs',
            costPrice: prod.cost_price || 0,
            sellingPrice: prod.selling_price || 0,
            currentStock: prod.current_stock || 0,
            status: prod.status || 'ACTIVE',
          },
          update: {
            skuBarcode: cleanBarcode,
            name: prod.name.trim(),
            unit: prod.unit ? prod.unit.trim() : 'pcs',
            costPrice: prod.cost_price,
            sellingPrice: prod.selling_price,
            currentStock: prod.current_stock,
            status: prod.status,
          },
        });

        syncedProductIds.push(prod.id);
      } catch (err) {
        failedItems.push({
          id: prod.id,
          entity: 'product',
          name: prod.name,
          reason: err.message,
        });
      }
    }

    // 2. Proses Sinkronisasi Transaksi (Idempotent & Atomic per transaksi)
    for (const txData of transactions) {
      try {
        // Cek apakah transaksi sudah pernah tersimpan (idempotent key via UUID)
        const existingTx = await prisma.stockTransaction.findUnique({
          where: { id: txData.id },
        });

        if (existingTx) {
          syncedTransactionIds.push(txData.id);
          continue;
        }

        // Jalankan transaksi atomik untuk tiap transaksi
        await prisma.$transaction(async (tx) => {
          const business = await tx.business.findUnique({
            where: { id: businessId },
            select: { code: true },
          });

          const currentYear = new Date().getFullYear();
          let txNumber = txData.transaction_number;
          if (!txNumber) {
            const count = await tx.stockTransaction.count({
              where: {
                businessId,
                createdAt: {
                  gte: new Date(currentYear, 0, 1),
                  lte: new Date(currentYear, 11, 31, 23, 59, 59, 999),
                },
              },
            });
            txNumber = `${business.code}-${currentYear}-${String(count + 1).padStart(6, '0')}`;
          }

          // Validasi produk
          const productIds = txData.items.map((i) => i.product_id);
          const prods = await tx.product.findMany({
            where: {
              id: { in: productIds },
              businessId,
            },
          });

          if (prods.length !== productIds.length) {
            throw new Error('Satu atau lebih produk dalam transaksi tidak ditemukan di server.');
          }

          const prodMap = new Map(prods.map((p) => [p.id, p]));

          // Validasi anti-stok minus jika STOCK_OUT
          if (txData.type === 'STOCK_OUT') {
            for (const item of txData.items) {
              const p = prodMap.get(item.product_id);
              if (p.currentStock < item.quantity) {
                throw new Error(
                  `Stok tidak mencukupi untuk '${p.name}'. Stok tersedia: ${p.currentStock} ${p.unit}, diminta keluar: ${item.quantity} ${p.unit}.`
                );
              }
            }
          }

          // Buat record transaksi
          const createdTx = await tx.stockTransaction.create({
            data: {
              id: txData.id,
              businessId,
              transactionNumber: txNumber,
              type: txData.type,
              notes: txData.notes || null,
              createdBy: userId,
              transactionAt: txData.transaction_at ? new Date(txData.transaction_at) : new Date(),
            },
          });

          // Buat items dan update stok
          for (const item of txData.items) {
            const p = prodMap.get(item.product_id);
            const itemId = item.id || uuidv4();

            await tx.stockTransactionItem.create({
              data: {
                id: itemId,
                businessId,
                transactionId: createdTx.id,
                productId: p.id,
                quantity: item.quantity,
                unitCostSnapshot: p.costPrice,
                createdAt: createdTx.transactionAt,
              },
            });

            const delta = txData.type === 'STOCK_IN' ? item.quantity : -item.quantity;
            await tx.product.update({
              where: { id: p.id },
              data: {
                currentStock: {
                  increment: delta,
                },
              },
            });
          }
        });

        syncedTransactionIds.push(txData.id);
      } catch (err) {
        failedItems.push({
          id: txData.id,
          entity: 'transaction',
          reason: err.message,
        });
      }
    }

    return res.status(200).json({
      success: true,
      message: `Sinkronisasi selesai: ${syncedProductIds.length} produk dan ${syncedTransactionIds.length} transaksi berhasil disinkronkan.`,
      data: {
        synced_product_ids: syncedProductIds,
        synced_transaction_ids: syncedTransactionIds,
        failed_items: failedItems,
      },
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  pullSync,
  pushSync,
};
