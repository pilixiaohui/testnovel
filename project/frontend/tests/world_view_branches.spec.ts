import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { useWorldStore } from '@/stores/world'
import WorldView from '../src/views/WorldView.vue'
import * as entityApi from '@/api/entity'
import * as anchorApi from '@/api/anchor'
import * as subplotApi from '@/api/subplot'

const routeState = vi.hoisted(() => ({
  name: 'world',
  params: { sceneId: '', rootId: '', branchId: '' },
  query: {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
}))

vi.mock('@/api/entity', () => ({
  fetchEntities: vi.fn(),
  createEntity: vi.fn(),
  updateEntity: vi.fn(),
  deleteEntity: vi.fn(),
  fetchRelations: vi.fn(),
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: vi.fn(),
}))

vi.mock('@/api/subplot', () => ({
  fetchSubplots: vi.fn(),
}))

const entityApiMock = vi.mocked(entityApi) as unknown as {
  fetchEntities: ReturnType<typeof vi.fn>
  createEntity: ReturnType<typeof vi.fn>
  updateEntity: ReturnType<typeof vi.fn>
  deleteEntity: ReturnType<typeof vi.fn>
  fetchRelations: ReturnType<typeof vi.fn>
}

const anchorApiMock = vi.mocked(anchorApi) as unknown as {
  fetchAnchors: ReturnType<typeof vi.fn>
}

const subplotApiMock = vi.mocked(subplotApi) as unknown as {
  fetchSubplots: ReturnType<typeof vi.fn>
}

const mountWorld = (setupStore?: (projectStore: ReturnType<typeof useProjectStore>, worldStore: ReturnType<typeof useWorldStore>) => void) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const projectStore = useProjectStore()
  const worldStore = useWorldStore()
  setupStore?.(projectStore, worldStore)

  const errors: unknown[] = []
  const wrapper = mount(WorldView, {
    global: {
      plugins: [pinia],
      stubs: {
        StateExtractPanel: true,
      },
      config: {
        errorHandler: (err) => {
          errors.push(err)
        },
      },
    },
  })
  return { wrapper, projectStore, worldStore, errors }
}

describe('WorldView branch coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params = { sceneId: '', rootId: '', branchId: '' }
    routeState.query = {}
    entityApiMock.fetchEntities.mockResolvedValue([])
    anchorApiMock.fetchAnchors.mockResolvedValue([])
    subplotApiMock.fetchSubplots.mockResolvedValue([])
    entityApiMock.createEntity.mockResolvedValue({ id: 'entity-1' })
    entityApiMock.updateEntity.mockResolvedValue({ ok: true })
    entityApiMock.deleteEntity.mockResolvedValue({ ok: true })
    entityApiMock.fetchRelations.mockResolvedValue([])
  })

  it('syncs from route when project context is missing', () => {
    const { projectStore } = mountWorld((project, world) => {
      project.root_id = ''
      project.branch_id = ''
      world.reset()
      vi.spyOn(project, 'syncFromRoute')
    })

    expect(projectStore.syncFromRoute).toHaveBeenCalled()
  })

  it('captures errors when load requires root or branch id', async () => {
    const { wrapper, projectStore, errors } = mountWorld((project) => {
      project.root_id = ''
      project.branch_id = ''
    })

    const loadButton = wrapper.find('[data-test="world-load"]')
    await loadButton.trigger('click')

    expect((errors[0] as Error).message).toBe('root_id is required')

    errors.length = 0
    projectStore.root_id = 'root-alpha'
    projectStore.branch_id = ''

    await loadButton.trigger('click')
    expect((errors[0] as Error).message).toBe('branch_id is required')
  })

  it('handles create entity when backend does not return id', async () => {
    entityApiMock.createEntity.mockResolvedValue({})

    const { wrapper, projectStore } = mountWorld((project) => {
      project.root_id = 'root-alpha'
      project.branch_id = 'main'
    })

    const createButton = wrapper.find('[data-test="world-entity-create"]')
    await createButton.trigger('click')

    expect(entityApiMock.createEntity).toHaveBeenCalledWith(
      projectStore.root_id,
      projectStore.branch_id,
      expect.objectContaining({ name: 'New Entity' }),
    )
  })

  it('captures errors when updating or deleting without target entity', async () => {
    const { wrapper, projectStore, worldStore, errors } = mountWorld((project, world) => {
      project.root_id = 'root-alpha'
      project.branch_id = 'main'
      world.reset()
    })

    const updateButton = wrapper.find('[data-test="world-entity-update"]')
    await updateButton.trigger('click')
    expect((errors[0] as Error).message).toBe('entity id is required')

    errors.length = 0
    const deleteButton = wrapper.find('[data-test="world-entity-delete"]')
    await deleteButton.trigger('click')
    expect((errors[0] as Error).message).toBe('entity id is required')

    errors.length = 0
    worldStore.setEntities([
      {
        id: 'entity-9',
        created_at: '2024-01-01',
        name: 'Entity',
        type: 'character',
        position: { x: 0, y: 0, z: 0 },
      },
    ])

    await updateButton.trigger('click')
    await deleteButton.trigger('click')

    expect(entityApiMock.updateEntity).toHaveBeenCalledWith(
      projectStore.root_id,
      projectStore.branch_id,
      'entity-9',
      expect.objectContaining({ name: 'Updated Entity' }),
    )
    expect(entityApiMock.deleteEntity).toHaveBeenCalledWith(
      projectStore.root_id,
      projectStore.branch_id,
      'entity-9',
    )
  })

  it('handles relation graph errors', async () => {
    entityApiMock.fetchRelations.mockRejectedValue(new Error('relation failed'))

    const { wrapper, projectStore } = mountWorld((project) => {
      project.root_id = 'root-alpha'
      project.branch_id = 'main'
    })

    const relationsButton = wrapper.find('[data-test="world-relations-show"]')
    await relationsButton.trigger('click')

    expect(entityApiMock.fetchRelations).toHaveBeenCalledWith(projectStore.root_id, projectStore.branch_id)
    expect(wrapper.find('[data-test="world-relations-graph"]').exists()).toBe(false)
  })
})
