import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { usePolling } from '@/composables/usePolling'
import { useNotification } from '@/composables/useNotification'

describe('M1-T4 composables', () => {
  describe('usePolling', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('throws when interval is invalid', () => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          usePolling(callback, 0)
          return {}
        },
        template: '<div />',
      })

      expect(() => mount(TestComponent)).toThrow('interval is required')
    })

    it('starts and stops polling', () => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          return usePolling(callback, 500)
        },
        template: '<div />',
      })

      const wrapper = mount(TestComponent)
      const vm = wrapper.vm as unknown as {
        start: () => void
        stop: () => void
        isPolling: boolean
      }

      vm.start()
      expect(vm.isPolling).toBe(true)

      vi.advanceTimersByTime(1600)
      expect(callback).toHaveBeenCalledTimes(3)

      vm.stop()
      expect(vm.isPolling).toBe(false)

      vi.advanceTimersByTime(1000)
      expect(callback).toHaveBeenCalledTimes(3)
    })
  })

  describe('useNotification', () => {
    it('stores and clears notifications', () => {
      const TestComponent = defineComponent({
        setup() {
          return useNotification()
        },
        template: '<div />',
      })

      const wrapper = mount(TestComponent)
      const vm = wrapper.vm as unknown as {
        items: Array<{ id: number; message: string }>
        count: number
        notify: (type: 'info' | 'success' | 'warning' | 'error', message: string) => number
        remove: (id: number) => void
        clear: () => void
      }

      const firstId = vm.notify('info', 'Ready')
      const secondId = vm.notify('success', 'Saved')

      expect(vm.items.length).toBe(2)
      expect(vm.count).toBe(2)
      expect(vm.items[0].id).toBe(secondId)

      vm.remove(firstId)
      expect(vm.items.length).toBe(1)

      vm.clear()
      expect(vm.items.length).toBe(0)
      expect(vm.count).toBe(0)
    })

    it('rejects empty messages', () => {
      const TestComponent = defineComponent({
        setup() {
          return useNotification()
        },
        template: '<div />',
      })

      const wrapper = mount(TestComponent)
      const vm = wrapper.vm as unknown as {
        notify: (type: 'info' | 'success' | 'warning' | 'error', message: string) => number
      }

      expect(() => vm.notify('info', '  ')).toThrow('message is required')
    })
  })
})
