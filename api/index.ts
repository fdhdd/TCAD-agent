import express from 'express';
import cors from 'cors';
import { chatRouter } from './routes/chat.js';
import { scriptRouter } from './routes/script.js';
import { simulationRouter } from './routes/simulation.js';
import { reportRouter } from './routes/report.js';

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3002;

app.use(cors());
app.use(express.json());

app.use('/api/chat', chatRouter);
app.use('/api/script', scriptRouter);
app.use('/api/simulation', simulationRouter);
app.use('/api/report', reportRouter);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'TCAD Agent API is running' });
});

app.listen(PORT, () => {
  console.log(`TCAD Agent API server running on http://localhost:${PORT}`);
});
