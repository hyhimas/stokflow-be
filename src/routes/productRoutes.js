const express = require('express');
const router = express.Router();
const productController = require('../controllers/productController');
const { authenticateJWT, authorizeRoles } = require('../middlewares/auth');
const { validateBody, validateQuery } = require('../middlewares/validate');
const {
  createProductSchema,
  updateProductSchema,
  getProductsQuerySchema,
} = require('../validators/productValidator');

router.get(
  '/',
  authenticateJWT,
  validateQuery(getProductsQuerySchema),
  productController.getProducts
);

router.get(
  '/:id',
  authenticateJWT,
  productController.getProductById
);

router.post(
  '/',
  authenticateJWT,
  authorizeRoles('OWNER'),
  validateBody(createProductSchema),
  productController.createProduct
);

router.put(
  '/:id',
  authenticateJWT,
  authorizeRoles('OWNER'),
  validateBody(updateProductSchema),
  productController.updateProduct
);

router.patch(
  '/:id/archive',
  authenticateJWT,
  authorizeRoles('OWNER'),
  productController.archiveProduct
);

module.exports = router;
