import { describe, expect, it } from 'vitest'
import { buildNavigationTarget } from '@/utils/navigation'

describe('navigation context target', () => {
  it('returns plain path when project context is missing', () => {
    expect(
      buildNavigationTarget('/editor', {
        root_id: '',
        branch_id: '',
        scene_id: '',
      }),
    ).toEqual({ path: '/editor' })
  })

  it('adds root and branch query for project routes', () => {
    expect(
      buildNavigationTarget('/snowflake', {
        root_id: 'root-alpha',
        branch_id: 'main',
        scene_id: '',
      }),
    ).toEqual({
      path: '/snowflake',
      query: {
        root_id: 'root-alpha',
        branch_id: 'main',
      },
    })
  })

  it('keeps scene id in path for editor and simulation routes', () => {
    expect(
      buildNavigationTarget('/editor', {
        root_id: 'root-alpha',
        branch_id: 'main',
        scene_id: 'scene-alpha',
      }),
    ).toEqual({
      path: '/editor/scene-alpha',
      query: {
        root_id: 'root-alpha',
        branch_id: 'main',
      },
    })

    expect(
      buildNavigationTarget('/simulation', {
        root_id: 'root-alpha',
        branch_id: 'main',
        scene_id: 'scene-beta',
      }),
    ).toEqual({
      path: '/simulation/scene-beta',
      query: {
        root_id: 'root-alpha',
        branch_id: 'main',
      },
    })
  })

  it('does not inject project query for non-project routes', () => {
    expect(
      buildNavigationTarget('/settings', {
        root_id: 'root-alpha',
        branch_id: 'main',
        scene_id: 'scene-alpha',
      }),
    ).toEqual({ path: '/settings' })
  })
})
