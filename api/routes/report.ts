import express from 'express';
import { generateReport } from '../services/analysisService.js';

const router = express.Router();

router.post('/generate', async (req, res) => {
  try {
    const { simulationId } = req.body;
    const report = await generateReport(simulationId);
    res.json({ report });
  } catch (error) {
    res.status(500).json({ error: 'Failed to generate report' });
  }
});

export { router as reportRouter };
