const { v4: uuidv4 } = require('uuid');
const prisma = require('../config/prisma');

const getProducts = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const {
      search,
      barcode,
      status,
      stock_status,
      unit,
      sort_by,
      sort_order,
      page,
      limit,
    } = req.validatedQuery;

    const where = {
      businessId,
    };

    // 1. Filter Status
    if (status && status !== 'ALL') {
      where.status = status;
    }

    // 2. Exact Barcode Scan (FR-11)
    if (barcode && barcode.trim() !== '') {
      where.skuBarcode = barcode.trim();
    }

    // 3. Search case-insensitive name or skuBarcode (FR-09)
    if (search && search.trim() !== '') {
      const cleanSearch = search.trim();
      where.OR = [
        { name: { contains: cleanSearch, mode: 'insensitive' } },
        { skuBarcode: { contains: cleanSearch, mode: 'insensitive' } },
      ];
    }

    // 4. Filter Stock Status
    if (stock_status === 'AVAILABLE') {
      where.currentStock = { gt: 0 };
    } else if (stock_status === 'EMPTY') {
      where.currentStock = 0;
    }

    // 5. Filter Satuan (Unit)
    if (unit && unit.trim() !== '') {
      where.unit = { equals: unit.trim(), mode: 'insensitive' };
    }

    // 6. Sorting Map
    const sortFieldMap = {
      name: 'name',
      current_stock: 'currentStock',
      selling_price: 'sellingPrice',
      cost_price: 'costPrice',
      updated_at: 'updatedAt',
      created_at: 'createdAt',
    };
    const orderByField = sortFieldMap[sort_by] || 'updatedAt';
    const orderByDirection = sort_order.toLowerCase() === 'asc' ? 'asc' : 'desc';

    // 7. Pagination Count & Query
    const skip = (page - 1) * limit;

    const [total, products] = await Promise.all([
      prisma.product.count({ where }),
      prisma.product.findMany({
        where,
        orderBy: { [orderByField]: orderByDirection },
        skip,
        take: limit,
      }),
    ]);

    const totalPages = Math.ceil(total / limit) || 1;

    return res.status(200).json({
      success: true,
      data: products,
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

const getProductById = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const { id } = req.params;

    const product = await prisma.product.findFirst({
      where: {
        id,
        businessId,
      },
      include: {
        transactionItems: {
          take: 10,
          orderBy: { createdAt: 'desc' },
          include: {
            transaction: {
              select: {
                id: true,
                transactionNumber: true,
                type: true,
                transactionAt: true,
                notes: true,
              },
            },
          },
        },
      },
    });

    if (!product) {
      return res.status(404).json({
        success: false,
        message: 'Produk tidak ditemukan.',
        errors: [`Product with id ${id} not found`],
      });
    }

    // Format riwayat mutasi stok 10 transaksi terakhir
    const mutationHistory = product.transactionItems.map((item) => ({
      item_id: item.id,
      transaction_id: item.transaction.id,
      transaction_number: item.transaction.transactionNumber,
      type: item.transaction.type,
      quantity: item.quantity,
      unit_cost_snapshot: item.unitCostSnapshot,
      transaction_at: item.transaction.transactionAt,
      notes: item.transaction.notes,
    }));

    const { transactionItems, ...productData } = product;

    return res.status(200).json({
      success: true,
      data: {
        ...productData,
        recent_mutation_history: mutationHistory,
      },
    });
  } catch (error) {
    next(error);
  }
};

const createProduct = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const {
      id,
      sku_barcode,
      name,
      unit,
      cost_price,
      selling_price,
      current_stock,
    } = req.body;

    const cleanBarcode = sku_barcode && sku_barcode.trim() !== '' ? sku_barcode.trim() : null;

    // FR-07: Validasi duplikasi sku_barcode dalam businessId yang sama
    if (cleanBarcode) {
      const existingBarcode = await prisma.product.findFirst({
        where: {
          businessId,
          skuBarcode: cleanBarcode,
          status: 'ACTIVE',
        },
      });

      if (existingBarcode) {
        return res.status(409).json({
          success: false,
          message: 'Kode barcode sudah digunakan oleh produk lain di toko ini',
          errors: [`Barcode '${cleanBarcode}' already used by active product '${existingBarcode.name}'`],
        });
      }
    }

    // Idempotent check jika client Flutter mengirimkan UUID yang sudah ada
    const productId = id || uuidv4();
    const existingProduct = await prisma.product.findUnique({
      where: { id: productId },
    });

    if (existingProduct) {
      return res.status(200).json({
        success: true,
        message: 'Produk sudah tersimpan sebelumnya (idempotent).',
        data: existingProduct,
      });
    }

    const product = await prisma.product.create({
      data: {
        id: productId,
        businessId,
        skuBarcode: cleanBarcode,
        name: name.trim(),
        unit: unit ? unit.trim() : 'pcs',
        costPrice: cost_price !== undefined ? cost_price : 0,
        sellingPrice: selling_price !== undefined ? selling_price : 0,
        currentStock: current_stock !== undefined ? current_stock : 0,
        status: 'ACTIVE',
      },
    });

    return res.status(201).json({
      success: true,
      message: 'Produk berhasil ditambahkan.',
      data: product,
    });
  } catch (error) {
    next(error);
  }
};

const updateProduct = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const { id } = req.params;
    const {
      sku_barcode,
      name,
      unit,
      cost_price,
      selling_price,
      current_stock,
      status,
    } = req.body;

    // Cek apakah produk milik bisnis ini
    const existingProduct = await prisma.product.findFirst({
      where: {
        id,
        businessId,
      },
    });

    if (!existingProduct) {
      return res.status(404).json({
        success: false,
        message: 'Produk tidak ditemukan.',
        errors: [`Product with id ${id} not found in this business`],
      });
    }

    // Validasi barcode duplikat jika barcode diubah
    let cleanBarcode = undefined;
    if (sku_barcode !== undefined) {
      cleanBarcode = sku_barcode && sku_barcode.trim() !== '' ? sku_barcode.trim() : null;
      if (cleanBarcode && cleanBarcode !== existingProduct.skuBarcode) {
        const duplicate = await prisma.product.findFirst({
          where: {
            businessId,
            skuBarcode: cleanBarcode,
            status: 'ACTIVE',
            NOT: { id },
          },
        });

        if (duplicate) {
          return res.status(409).json({
            success: false,
            message: 'Kode barcode sudah digunakan oleh produk lain di toko ini',
            errors: [`Barcode '${cleanBarcode}' already used by product '${duplicate.name}'`],
          });
        }
      }
    }

    const updateData = {};
    if (name !== undefined) updateData.name = name.trim();
    if (cleanBarcode !== undefined) updateData.skuBarcode = cleanBarcode;
    if (unit !== undefined) updateData.unit = unit.trim();
    if (cost_price !== undefined) updateData.costPrice = cost_price;
    if (selling_price !== undefined) updateData.sellingPrice = selling_price;
    if (current_stock !== undefined) updateData.currentStock = current_stock;
    if (status !== undefined) updateData.status = status;

    const updatedProduct = await prisma.product.update({
      where: { id },
      data: updateData,
    });

    return res.status(200).json({
      success: true,
      message: 'Informasi produk berhasil diperbarui.',
      data: updatedProduct,
    });
  } catch (error) {
    next(error);
  }
};

const archiveProduct = async (req, res, next) => {
  try {
    const businessId = req.user.businessId;
    const { id } = req.params;

    const existingProduct = await prisma.product.findFirst({
      where: {
        id,
        businessId,
      },
    });

    if (!existingProduct) {
      return res.status(404).json({
        success: false,
        message: 'Produk tidak ditemukan.',
        errors: [`Product with id ${id} not found`],
      });
    }

    const archivedProduct = await prisma.product.update({
      where: { id },
      data: { status: 'ARCHIVED' },
    });

    return res.status(200).json({
      success: true,
      message: 'Produk berhasil diarsipkan (soft delete). Riwayat transaksi tetap utuh.',
      data: archivedProduct,
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getProducts,
  getProductById,
  createProduct,
  updateProduct,
  archiveProduct,
};
