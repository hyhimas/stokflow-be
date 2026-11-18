const express = require('express');
const router = express.Router();
const syncController = require('../controllers/syncController');
const { authenticateJWT } = require('../middlewares/auth');
const { validateBody, validateQuery } = require('../middlewares/validate');
const { syncPushSchema, syncPullQuerySchema } = require('../validators/syncValidator');

router.get(
  '/pull',
  authenticateJWT,
  validateQuery(syncPullQuerySchema),
  syncController.pullSync
);

router.post(
  '/push',
  authenticateJWT,
  validateBody(syncPushSchema),
  syncController.pushSync
);

module.exports = router;
