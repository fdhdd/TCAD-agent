import express from 'express';
import { readScript, writeScript, parseScript } from '../services/scriptService.js';
import { generateTCADScriptFromDescription } from '../services/agentService.js';

const router = express.Router();

router.post('/read', async (req, res) => {
  try {
    const { path } = req.body;
    const script = await readScript(path);
    res.json({ script });
  } catch (error) {
    res.status(500).json({ error: 'Failed to read script' });
  }
});

router.post('/write', async (req, res) => {
  try {
    const { script } = req.body;
    const result = await writeScript(script);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: 'Failed to write script' });
  }
});

router.post('/parse', async (req, res) => {
  try {
    const { content, type } = req.body;
    const parameters = await parseScript(content, type);
    res.json({ parameters });
  } catch (error) {
    res.status(500).json({ error: 'Failed to parse script' });
  }
});

router.get('/sample', async (req, res) => {
  try {
    // Return a sample TCAD script
    const sampleScript = `# Sample TCAD Script
# This is a basic sdevice simulation script

# Define the device structure
device {
  name = "MOSFET"
  type = "MOSFET"
  
  # Material properties
  silicon {
    doping = 1e15
    mobility = 400
  }
  
  # Contacts
  source {
    voltage = 0.0
  }
  
  drain {
    voltage = 1.0
  }
  
  gate {
    voltage = 0.5
  }
}

# Simulation parameters
solve {
  type = "DC"
  method = "Newton"
  tolerance = 1e-6
}

# Output
output {
  current = true
  potential = true
  electric_field = true
}`;
    
    res.json({ script: sampleScript });
  } catch (error) {
    res.status(500).json({ error: 'Failed to load sample script' });
  }
});

router.post('/generate', async (req, res) => {
  try {
    const { description, type } = req.body;
    const script = await generateTCADScriptFromDescription(description, type);
    res.json({ script });
  } catch (error) {
    res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to generate script' });
  }
});

export { router as scriptRouter };
