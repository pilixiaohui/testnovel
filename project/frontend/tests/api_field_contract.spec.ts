import { beforeEach, describe, expect, it, vi } from 'vitest'

const postMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/index', () => ({
  apiClient: {
    post: postMock,
  },
}))

const loadBranchApi = async () => await import('@/api/branch')

describe('branch api request body contract', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('resetBranch sends commit_id and does not send target_commit_id', async () => {
    postMock.mockResolvedValueOnce({ ok: true })

    const { branchApi } = await loadBranchApi()
    await branchApi.resetBranch('root-alpha', 'branch-alpha', 'commit-1')

    expect(postMock).toHaveBeenCalledTimes(1)
    const [url, body] = postMock.mock.calls[0]
    expect(url).toBe('/roots/root-alpha/branches/branch-alpha/reset')
    expect(body).toHaveProperty('commit_id', 'commit-1')
    expect(body).not.toHaveProperty('target_commit_id')
  })

  it('forkFromScene sends source_branch_id in payload', async () => {
    postMock.mockResolvedValueOnce({ ok: true })

    const { branchApi } = await loadBranchApi()
    const forkFromScene = branchApi.forkFromScene as unknown as (
      rootId: string,
      sceneOriginId: string,
      newBranchId: string,
      sourceBranchId: string,
    ) => Promise<unknown>

    await forkFromScene('root-alpha', 'scene-alpha', 'branch-new', 'branch-src')

    expect(postMock).toHaveBeenCalledTimes(1)
    const [url, body] = postMock.mock.calls[0]
    expect(url).toBe('/roots/root-alpha/branches/fork_from_scene')
    expect(body).toMatchObject({
      scene_origin_id: 'scene-alpha',
      new_branch_id: 'branch-new',
      source_branch_id: 'branch-src',
    })
  })
})
