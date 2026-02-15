import { describe, expect, it } from 'vitest'
import { resolveActivePath } from '../src/utils/navigation'

describe('resolveActivePath', () => {
  it('normalizes snowflake detail paths to base route', () => {
    expect(resolveActivePath('/snowflake/root-alpha')).toBe('/snowflake')
  })

  it('normalizes editor and simulation scene paths to base routes', () => {
    expect(resolveActivePath('/editor/scene-alpha')).toBe('/editor')
    expect(resolveActivePath('/simulation/scene-alpha')).toBe('/simulation')
  })

  it('returns original path for base routes', () => {
    expect(resolveActivePath('/')).toBe('/')
    expect(resolveActivePath('/settings')).toBe('/settings')
    expect(resolveActivePath('/world')).toBe('/world')
  })
})
