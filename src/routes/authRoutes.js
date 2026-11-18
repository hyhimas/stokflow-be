const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');
const { authenticateJWT } = require('../middlewares/auth');
const { validateBody } = require('../middlewares/validate');
const { registerSchema, loginSchema } = require('../validators/authValidator');

router.post('/register', validateBody(registerSchema), authController.register);
router.post('/login', validateBody(loginSchema), authController.login);
router.get('/me', authenticateJWT, authController.getMe);
router.post('/logout', authenticateJWT, authController.logout);

module.exports = router;
