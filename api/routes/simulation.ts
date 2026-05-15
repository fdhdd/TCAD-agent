import express from 'express';
import { runSimulation, getSimulationStatus, stopSimulation, resetSimulation, testScriptExecution } from '../services/simulationService.js';

const router = express.Router();

router.post('/run', async (req, res) => {
  try {
    const { scriptId, parameters } = req.body;
    const simulationId = await runSimulation(scriptId, parameters);
    res.json({ simulationId });
  } catch (error) {
    res.status(500).json({ error: 'Failed to start simulation' });
  }
});

router.post('/test', async (req, res) => {
  try {
    const { script } = req.body;
    const result = await testScriptExecution(script);
    res.json(result);
  } catch (error) {
    res.status(500).json({ 
      success: false, 
      error: error instanceof Error ? error.message : 'Test failed',
      logs: [] 
    });
  }
});

router.get('/status/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const status = await getSimulationStatus(id);
    res.json(status);
  } catch (error) {
    res.status(500).json({ error: 'Failed to get simulation status' });
  }
});

router.post('/stop', async (req, res) => {
  try {
    const { simulationId } = req.body;
    await stopSimulation(simulationId);
    const status = await getSimulationStatus(simulationId);
    res.json({ status });
  } catch (error) {
    res.status(500).json({ error: 'Failed to stop simulation' });
  }
});

router.post('/reset', async (req, res) => {
  try {
    const { simulationId } = req.body;
    await resetSimulation(simulationId);
    const status = await getSimulationStatus(simulationId);
    res.json({ status });
  } catch (error) {
    res.status(500).json({ error: 'Failed to reset simulation' });
  }
});

export { router as simulationRouter };
