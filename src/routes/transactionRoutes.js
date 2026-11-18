const express = require('express');
const router = express.Router();
const transactionController = require('../controllers/transactionController');
const { authenticateJWT, authorizeRoles } = require('../middlewares/auth');
const { validateBody, validateQuery } = require('../middlewares/validate');
const {
  createTransactionSchema,
  getTransactionsQuerySchema,
} = require('../validators/transactionValidator');

router.get(
  '/',
  authenticateJWT,
  validateQuery(getTransactionsQuerySchema),
  transactionController.getTransactions
);

router.get(
  '/:id',
  authenticateJWT,
  transactionController.getTransactionById
);

router.post(
  '/',
  authenticateJWT,
  authorizeRoles('OWNER', 'STAFF'),
  validateBody(createTransactionSchema),
  transactionController.createTransaction
);

module.exports = router;
