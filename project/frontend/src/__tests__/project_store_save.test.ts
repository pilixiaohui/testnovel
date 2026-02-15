import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '../stores/project'
import { commitApi } from '@/api/commit'

vi.mock('@/api/commit', () => ({
  commitApi: {
    commitScene: vi.fn(),
  },
}))

describe('project store saveProjectData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('setLoading toggles loading state', () => {
    const store = useProjectStore()

    store.setLoading(true)
    expect(store.is_loading).toBe(true)

    store.setLoading(false)
    expect(store.is_loading).toBe(false)
  })

  it('saveProjectData rejects missing root_id', async () => {
    const store = useProjectStore()
    await expect(store.saveProjectData('', { expected_outcome: 'summary' })).rejects.toThrow('root_id is required')
  })

  it('saveProjectData rejects missing branch_id', async () => {
    const store = useProjectStore()
    store.setProject('root-alpha', '', 'scene-alpha')
    await expect(store.saveProjectData('root-alpha', { expected_outcome: 'summary' })).rejects.toThrow('branch_id is required')
  })

  it('saveProjectData rejects missing scene_id', async () => {
    const store = useProjectStore()
    store.setProject('root-alpha', 'main', '')
    await expect(store.saveProjectData('root-alpha', { expected_outcome: 'summary' })).rejects.toThrow('scene_id is required')
  })

  it('saveProjectData rejects missing content', async () => {
    const store = useProjectStore()
    store.setProject('root-alpha', 'main', 'scene-alpha')
    await expect(store.saveProjectData('root-alpha', {})).rejects.toThrow('content is required')
  })

  it('saveProjectData commits with scene context', async () => {
    const store = useProjectStore()
    store.setProject('root-alpha', 'main', 'scene-alpha')

    vi.mocked(commitApi.commitScene).mockResolvedValue({
      commit_id: 'commit-alpha',
      scene_version_ids: ['version-alpha'],
    })

    const payload = {
      expected_outcome: 'summary',
      conflict_type: 'internal',
      actual_outcome: 'success',
      rendered_content: 'content',
    }
    const result = await store.saveProjectData('root-alpha', payload)

    expect(commitApi.commitScene).toHaveBeenCalledWith('root-alpha', 'main', {
      scene_origin_id: 'scene-alpha',
      content: payload,
      message: 'Saved project data',
    })
    expect(result).toEqual({
      commit_id: 'commit-alpha',
      scene_version_ids: ['version-alpha'],
    })
    expect(store.is_loading).toBe(false)
  })
})
