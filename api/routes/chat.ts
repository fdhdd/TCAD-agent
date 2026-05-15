import express from 'express';
import { processChatMessage } from '../services/agentService.js';

const router = express.Router();

router.post('/', async (req, res) => {
  try {
    const { message, context } = req.body;
    const response = await processChatMessage(message, context);
    res.json(response);
  } catch (error) {
    res.status(500).json({ error: 'Failed to process chat message' });
  }
});

export { router as chatRouter };
