import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import HomeView from '../src/views/HomeView.vue'

const pushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

const mountHome = (setupStore?: (store: ReturnType<typeof useProjectStore>) => void) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useProjectStore()
  setupStore?.(store)
  const wrapper = mount(HomeView, { global: { plugins: [pinia] } })
  return { wrapper, store }
}

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('HomeView navigation and overview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders overview content and quick entries for active project', async () => {
    const { wrapper } = mountHome((store) => {
      store.root_id = 'root-alpha'
      store.projects = [
        {
          root_id: 'root-alpha',
          name: 'Project Alpha',
          created_at: '2025-01-01T10:00:00Z',
          updated_at: '2025-01-02T10:00:00Z',
        },
      ]
    })

    await flushPromises()

    expect(wrapper.find('.overview-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Project Alpha')

    const quickCards = wrapper.findAll('.quick-card')
    expect(quickCards.length).toBe(4)
  })

  it('shows empty overview when no current project', async () => {
    const { wrapper } = mountHome((store) => {
      store.root_id = ''
      store.projects = []
      vi.spyOn(store, 'listProjects').mockResolvedValue()
    })

    await flushPromises()

    expect(wrapper.find('.overview-empty').exists()).toBe(true)
  })

  it('selects project card and navigates to snowflake', async () => {
    const { wrapper, store } = mountHome((currentStore) => {
      currentStore.projects = [
        {
          root_id: 'root-2',
          name: 'Project Beta',
          created_at: '2025-02-01T10:00:00Z',
          updated_at: '2025-02-02T10:00:00Z',
        },
      ]
    })

    const loadSpy = vi.spyOn(store, 'loadProject').mockResolvedValue({})

    await flushPromises()

    const card = wrapper.find('[data-test="project-card"]')
    expect(card.exists()).toBe(true)
    await card.trigger('click')
    await flushPromises()

    expect(loadSpy).toHaveBeenCalledWith('root-2')
    expect(pushMock).toHaveBeenCalledWith('/snowflake')
  })

  it('prevents duplicate project creation requests on rapid clicks', async () => {
    const deferred = createDeferred<{
      root_id: string
      name: string
      created_at: string
      updated_at: string
    }>()

    const { wrapper, store } = mountHome((currentStore) => {
      vi.spyOn(currentStore, 'listProjects').mockResolvedValue()
    })

    const saveProjectSpy = vi.spyOn(store, 'saveProject').mockReturnValue(deferred.promise)
    const loadProjectSpy = vi.spyOn(store, 'loadProject').mockResolvedValue({})

    await flushPromises()

    const input = wrapper.find('[data-test="project-create-input"]')
    expect(input.exists()).toBe(true)
    await input.setValue('Project Locked')

    const button = wrapper.find('[data-test="create-project-btn"]')
    expect(button.exists()).toBe(true)

    await button.trigger('click')
    await button.trigger('click')

    expect(saveProjectSpy).toHaveBeenCalledTimes(1)

    deferred.resolve({
      root_id: 'root-lock-1',
      name: 'Project Locked',
      created_at: '2025-04-01T10:00:00Z',
      updated_at: '2025-04-01T10:00:00Z',
    })
    await flushPromises()

    expect(loadProjectSpy).toHaveBeenCalledWith('root-lock-1')
    expect(pushMock).toHaveBeenCalledWith('/snowflake')
  })

  it('routes via hero actions', async () => {
    const { wrapper } = mountHome((store) => {
      store.root_id = 'root-9'
      store.projects = [
        {
          root_id: 'root-9',
          name: 'Project Gamma',
          created_at: '2025-03-01T10:00:00Z',
          updated_at: '2025-03-02T10:00:00Z',
        },
      ]
    })

    await flushPromises()

    const buttons = wrapper.findAll('el-button')
    const snowflakeButton = buttons.find((button) => button.text().includes('开始雪花流程'))
    const settingsButton = buttons.find((button) => button.text().includes('系统设置'))

    expect(snowflakeButton).toBeDefined()
    expect(settingsButton).toBeDefined()

    await snowflakeButton!.trigger('click')
    await settingsButton!.trigger('click')

    expect(pushMock).toHaveBeenCalledWith('/snowflake')
    expect(pushMock).toHaveBeenCalledWith('/settings')
  })
})
