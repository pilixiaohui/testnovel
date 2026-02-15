import { computed } from 'vue'
import { useSimulationStore } from '../stores/simulation'

export const useSimulation = () => {
  const store = useSimulationStore()

  const status = computed(() => store.status)
  const isRunning = computed(() => store.isRunning)

  const start = () => {
    store.setStatus('running')
  }

  const stop = () => {
    store.setStatus('idle')
  }

  const reset = () => {
    store.reset()
  }

  return {
    store,
    status,
    isRunning,
    start,
    stop,
    reset,
  }
}
