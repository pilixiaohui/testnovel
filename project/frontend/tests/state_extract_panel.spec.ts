import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import StateExtractPanel from '../src/components/StateExtractPanel.vue'

const stateExtractMock = vi.hoisted(() => vi.fn())
const stateCommitMock = vi.hoisted(() => vi.fn())
const fetchAnchorsMock = vi.hoisted(() => vi.fn())
const fetchEntitiesMock = vi.hoisted(() => vi.fn())
const fetchSubplotsMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/llm', () => ({
  llmApi: {
    stateExtract: stateExtractMock,
    stateCommit: stateCommitMock,
  },
}))

vi.mock('@/api/anchor', () => ({
  fetchAnchors: fetchAnchorsMock,
}))

vi.mock('@/api/entity', () => ({
  fetchEntities: fetchEntitiesMock,
}))

vi.mock('@/api/subplot', () => ({
  fetchSubplots: fetchSubplotsMock,
}))

const baseProps = {
  rootId: 'root-alpha',
  branchId: 'main',
  context: {
    scene_id: 'scene-9',
    content: '测试内容',
    entity_ids: ['entity-1', 'entity-2'],
  },
}

const mountPanel = (props: Partial<typeof baseProps> = {}) =>
  mount(StateExtractPanel, {
    props: {
      ...baseProps,
      ...props,
      context: {
        ...baseProps.context,
        ...(props.context ?? {}),
      },
    },
  })

describe('StateExtractPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('extracts state and shows preview', async () => {
    const proposals = [{ id: 'p1', type: 'entity' }]
    stateExtractMock.mockResolvedValue(proposals)

    const wrapper = mountPanel()

    expect(wrapper.find('[data-test="extract-state-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="extract-results"]').exists()).toBe(true)

    await wrapper.find('[data-test="extract-state-btn"]').trigger('click')
    await flushPromises()

    expect(stateExtractMock).toHaveBeenCalledWith(
      expect.objectContaining({
        root_id: 'root-alpha',
        branch_id: 'main',
        scene_id: 'scene-9',
      }),
    )
    expect(wrapper.find('[data-test="state-extract-preview"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="state-commit"]').exists()).toBe(true)
  })

  it('shows error when extract payload is invalid', async () => {
    stateExtractMock.mockResolvedValue({ invalid: true })

    const wrapper = mountPanel()

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="state-extract-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="state-commit"]').exists()).toBe(false)
  })

  it('shows error when content is missing', async () => {
    const wrapper = mountPanel({
      context: {
        scene_id: 'scene-9',
        content: '',
        entity_ids: ['entity-1'],
      },
    })

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    expect(stateExtractMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="state-extract-error"]').exists()).toBe(true)
  })

  it('falls back to scene_entities for entity ids', async () => {
    stateExtractMock.mockResolvedValue([{ id: 'p-fallback' }])

    const wrapper = mountPanel({
      context: {
        scene_id: 'scene-9',
        content: 'fallback-content',
        entity_ids: [],
        scene_entities: [{ entity_id: 'entity-fallback' }],
      },
    })

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    expect(stateExtractMock).toHaveBeenCalledWith(
      expect.objectContaining({
        entity_ids: ['entity-fallback'],
      }),
    )
    expect(wrapper.find('[data-test="state-extract-preview"]').exists()).toBe(true)
  })

  it('loads fallback entity ids from entities API when context does not provide ids', async () => {
    fetchEntitiesMock.mockResolvedValue([
      { entity_id: 'entity-from-api-1' },
      { id: 'entity-from-api-2' },
    ])
    stateExtractMock.mockResolvedValue([{ id: 'p-api-fallback' }])

    const wrapper = mountPanel({
      context: {
        scene_id: 'scene-9',
        content: 'fallback-content',
        entity_ids: [],
        scene_entities: [],
      },
    })

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    expect(fetchEntitiesMock).toHaveBeenCalledWith('root-alpha', 'main')
    expect(stateExtractMock).toHaveBeenCalledWith(
      expect.objectContaining({
        entity_ids: ['entity-from-api-1', 'entity-from-api-2'],
      }),
    )
    expect(wrapper.find('[data-test="state-extract-preview"]').exists()).toBe(true)
  })

  it('shows error when root_id is missing', async () => {
    const wrapper = mountPanel({ rootId: '' })

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    expect(stateExtractMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="state-extract-error"]').exists()).toBe(true)
  })

  it('commits preview and emits refresh payload', async () => {
    const proposals = [{ id: 'p2', type: 'anchor' }]
    stateExtractMock.mockResolvedValue(proposals)
    stateCommitMock.mockResolvedValue({ status: 'ok' })
    fetchEntitiesMock.mockResolvedValue([{ id: 'e1' }])
    fetchAnchorsMock.mockResolvedValue(['Anchor 1'])
    fetchSubplotsMock.mockResolvedValue(['Subplot 1'])

    const wrapper = mountPanel()

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-test="state-commit"]').trigger('click')
    await flushPromises()

    expect(stateCommitMock).toHaveBeenCalledWith('root-alpha', 'main', proposals)
    expect(fetchEntitiesMock).toHaveBeenCalledWith('root-alpha', 'main')
    expect(fetchAnchorsMock).toHaveBeenCalledWith('root-alpha', 'main')
    expect(fetchSubplotsMock).toHaveBeenCalledWith('root-alpha', 'main')

    const refreshEvents = wrapper.emitted('refresh') || []
    expect(refreshEvents.length).toBe(1)
    const [payload] = refreshEvents[0] as unknown as Array<{
      entities: unknown[]
      anchors: unknown[]
      subplots: unknown[]
    }>
    expect(payload.entities).toEqual([{ id: 'e1' }])
    expect(payload.anchors).toEqual(['Anchor 1'])
    expect(payload.subplots).toEqual(['Subplot 1'])
    expect(wrapper.find('[data-test="state-commit-status"]').exists()).toBe(true)
  })

  it('shows commit error when commit fails', async () => {
    stateExtractMock.mockResolvedValue([{ id: 'p3' }])
    stateCommitMock.mockRejectedValue(new Error('commit failed'))

    const wrapper = mountPanel()

    await wrapper.find('[data-test="state-extract"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-test="state-commit"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="state-commit-error"]').exists()).toBe(true)
  })
})
