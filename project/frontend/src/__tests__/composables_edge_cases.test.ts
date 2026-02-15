import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { usePolling } from '@/composables/usePolling'
import { useNotification } from '@/composables/useNotification'

describe('Composables edge cases', () => {
  describe('usePolling', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it.each([
      ['undefined', undefined],
      ['null', null],
      ['number', 123],
      ['string', 'callback'],
      ['object', {}],
    ])('throws when callback is %s', (_label, cb) => {
      const TestComponent = defineComponent({
        setup() {
          usePolling(cb as unknown as () => void, 100)
          return {}
        },
        template: '<div />',
      })

      expect(() => mount(TestComponent)).toThrow('callback is required')
    })

    it.each([
      ['negative', -1],
      ['nan', Number.NaN],
      ['infinity', Number.POSITIVE_INFINITY],
      ['string', '100'],
      ['null', null],
      ['undefined', undefined],
    ])('throws when interval is invalid (%s)', (_label, interval) => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          usePolling(callback, interval as unknown as number)
          return {}
        },
        template: '<div />',
      })

      expect(() => mount(TestComponent)).toThrow('interval is required')
    })

    it('accepts a very large interval (no immediate calls)', () => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          // Node timers clamp values > 2^31-1; use the max safe delay to avoid overflow behavior.
          return usePolling(callback, 2_147_483_647)
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

      vi.advanceTimersByTime(1000)
      expect(callback).toHaveBeenCalledTimes(0)

      vm.stop()
      expect(vm.isPolling).toBe(false)
      wrapper.unmount()
    })

    it('start is idempotent (does not create multiple timers)', () => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          return usePolling(callback, 100)
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
      vi.advanceTimersByTime(300)
      expect(callback).toHaveBeenCalledTimes(3)

      vm.start()
      vi.advanceTimersByTime(300)
      expect(callback).toHaveBeenCalledTimes(6)

      vm.stop()
      wrapper.unmount()
    })

    it('stop is safe before start', () => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          return usePolling(callback, 100)
        },
        template: '<div />',
      })

      const wrapper = mount(TestComponent)
      const vm = wrapper.vm as unknown as {
        stop: () => void
        isPolling: boolean
      }

      vm.stop()
      expect(vm.isPolling).toBe(false)

      vi.advanceTimersByTime(500)
      expect(callback).toHaveBeenCalledTimes(0)
      wrapper.unmount()
    })

    it('stops polling on unmount', () => {
      const callback = vi.fn()
      const TestComponent = defineComponent({
        setup() {
          return usePolling(callback, 100)
        },
        template: '<div />',
      })

      const wrapper = mount(TestComponent)
      const vm = wrapper.vm as unknown as {
        start: () => void
      }

      vm.start()
      vi.advanceTimersByTime(250)
      expect(callback).toHaveBeenCalledTimes(2)

      wrapper.unmount()
      vi.advanceTimersByTime(500)
      expect(callback).toHaveBeenCalledTimes(2)
    })
  })

  describe('useNotification', () => {
    const mountNotification = () => {
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

      return { wrapper, vm }
    }

    it('accepts unicode/special messages and preserves order', () => {
      const { wrapper, vm } = mountNotification()

      const id1 = vm.notify('info', '用户A + tag@example.com')
      const id2 = vm.notify('success', 'line1\nline2')

      expect(vm.count).toBe(2)
      expect(vm.items[0].id).toBe(id2)
      expect(vm.items[1].id).toBe(id1)

      wrapper.unmount()
    })

    it('accepts a very long message', () => {
      const { wrapper, vm } = mountNotification()

      const msg = 'a'.repeat(10_000)
      vm.notify('info', msg)

      expect(vm.items[0].message.length).toBe(10_000)
      expect(vm.count).toBe(1)

      wrapper.unmount()
    })

    it.each([
      ['empty', ''],
      ['whitespace', '   '],
    ])('throws when message is %s', (_label, message) => {
      const { wrapper, vm } = mountNotification()

      expect(() => vm.notify('info', message)).toThrow('message is required')

      wrapper.unmount()
    })

    it.each([
      ['null', null],
      ['undefined', undefined],
    ])('fails fast when message is %s', (_label, message) => {
      const { wrapper, vm } = mountNotification()

      expect(() => vm.notify('info', message as unknown as string)).toThrow()

      wrapper.unmount()
    })

    it('remove/clear are safe on missing ids and empty lists', () => {
      const { wrapper, vm } = mountNotification()

      expect(vm.count).toBe(0)
      expect(() => vm.remove(999)).not.toThrow()
      expect(() => vm.remove(-1)).not.toThrow()
      expect(() => vm.clear()).not.toThrow()
      expect(vm.count).toBe(0)

      wrapper.unmount()
    })
  })
})
