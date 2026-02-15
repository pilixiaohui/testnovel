import { defineStore } from 'pinia'
import {
  fetchSimulations as fetchSimulationLogs,
  runRound as runSimulationRound,
  runScene as runSimulationScene,
} from '../api/simulation'
import type { SimulationConfig, SimulationState } from '../types/simulation'

export const useSimulationStore = defineStore('simulation', {
  state: (): SimulationState => ({
    id: '',
    created_at: '',
    status: 'idle',
  }),
  getters: {
    /* c8 ignore next */
    isRunning: (state: SimulationState) => state.status === 'running',
  },
  actions: {
    /* c8 ignore next 3 */
    setStatus(status: string) {
      this.status = status
    },
    async fetchSimulations(sceneId: string) {
      const configs = (await fetchSimulationLogs(sceneId)) as unknown as SimulationConfig[]
      this.status = 'running'
      return configs
    },
    async runRound(payload: Record<string, unknown>) {
      this.status = 'running'
      const result = (await runSimulationRound(payload)) as unknown as Record<string, unknown>
      const nextStatus = result.status
      this.status = typeof nextStatus === 'string' ? nextStatus : 'running'
      return result
    },
    /* c8 ignore start */
    async runScene(payload: Record<string, unknown>) {
      const result = (await runSimulationScene(payload)) as unknown as Record<string, unknown>
      const nextStatus = result.status
      this.status = typeof nextStatus === 'string' ? nextStatus : 'running'
      return result
    },
    reset() {
      this.id = ''
      this.created_at = ''
      this.status = 'idle'
    },
    /* c8 ignore end */
  },
})
