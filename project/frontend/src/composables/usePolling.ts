import { onUnmounted, ref } from 'vue'

export function usePolling(callback: () => Promise<void> | void, interval: number) {
  if (typeof callback !== 'function') {
    throw new Error('callback is required')
  }
  if (!Number.isFinite(interval) || interval <= 0) {
    throw new Error('interval is required')
  }

  const isPolling = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isPolling.value = false
  }

  const start = () => {
    if (timer) {
      clearInterval(timer)
    }
    isPolling.value = true
    timer = setInterval(() => {
      void callback()
    }, interval)
  }

  onUnmounted(stop)

  return { isPolling, start, stop }
}
