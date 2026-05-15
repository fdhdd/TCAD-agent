import type { SimulationResult } from '../../shared/types.js';
import { getSimulationStatus } from './simulationService.js';

export async function generateReport(simulationId: string): Promise<SimulationResult> {
  const status = await getSimulationStatus(simulationId);
  if (!status.result) {
    throw new Error('Simulation not completed yet');
  }
  return status.result;
}
