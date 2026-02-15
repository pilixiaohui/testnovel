import { computed, ref } from 'vue'

type NotificationType = 'info' | 'success' | 'warning' | 'error'

type NotificationItem = {
  id: number
  type: NotificationType
  message: string
  created_at: string
}

export function useNotification() {
  const items = ref<NotificationItem[]>([])
  let counter = 0

  const notify = (type: NotificationType, message: string) => {
    if (!message.trim()) {
      throw new Error('message is required')
    }

    counter += 1
    items.value = [
      {
        id: counter,
        type,
        message,
        created_at: new Date().toISOString(),
      },
      ...items.value,
    ]
    return counter
  }

  const remove = (id: number) => {
    items.value = items.value.filter((item) => item.id !== id)
  }

  const clear = () => {
    items.value = []
  }

  const count = computed(() => items.value.length)

  return { items, count, notify, remove, clear }
}
