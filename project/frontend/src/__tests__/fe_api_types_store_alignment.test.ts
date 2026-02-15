import { describe, it, expect, expectTypeOf } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { AxiosResponse } from 'axios'
import { useSimulationStore } from '../stores/simulation'
import { useSnowflakeStore } from '../stores/snowflake'
import type { SimulationConfig, SimulationState } from '../types/simulation'
import type { SnowflakeRoot, SnowflakeRootState } from '../types/snowflake'
import { fetchSimulations } from '../api/simulation'
import { fetchSnowflakeRoot } from '../api/snowflake'

describe('fe api types store alignment', () => {
  it('simulation store state matches SimulationState keys', () => {
    setActivePinia(createPinia())
    const store = useSimulationStore()
    const actualKeys = Object.keys(store.$state).sort()
    const expectedKeys: Array<keyof SimulationState> = ['id', 'created_at', 'status']
    expect(actualKeys).toEqual([...expectedKeys].sort())
  })

  it('snowflake store state matches SnowflakeRoot keys', () => {
    setActivePinia(createPinia())
    const store = useSnowflakeStore()
    const actualKeys = Object.keys(store.$state).sort()
    const expectedKeys: Array<keyof SnowflakeRootState> = ['id', 'created_at', 'steps']
    expect(actualKeys).toEqual([...expectedKeys].sort())
  })

  it('api functions are typed to core models', () => {
    expectTypeOf(fetchSimulations).returns.toEqualTypeOf<Promise<AxiosResponse<SimulationConfig[]>>>()
    expectTypeOf(fetchSnowflakeRoot).returns.toEqualTypeOf<Promise<AxiosResponse<SnowflakeRoot>>>()
  })
})
