import './element_plus_style_mock'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ActionTimeline from '../src/components/simulation/ActionTimeline.vue'
import type { SimulationRoundResult } from '@/types/simulation'

const makeRound = (overrides: Partial<SimulationRoundResult> = {}): SimulationRoundResult => ({
  round_id: 'r1',
  agent_actions: [
    {
      agent_id: 'agent-1',
      internal_thought: 'thinking',
      action_type: 'move',
      action_target: 'target',
      action_description: 'moves',
    },
  ],
  dm_arbitration: {
    round_id: 'r1',
    action_results: [],
    conflicts_resolved: [],
    environment_changes: [],
  },
  narrative_events: [],
  sensory_seeds: [],
  convergence_score: 0.2,
  drama_score: 0.1,
  info_gain: 0.3,
  stagnation_count: 0,
  ...overrides,
})

describe('ActionTimeline', () => {
  it('emits select and renders conflicts when present', async () => {
    const rounds = [
      makeRound({
        dm_arbitration: {
          round_id: 'r1',
          action_results: [],
          conflicts_resolved: [{ agents: ['A', 'B'], resolution: 'Resolved' }],
          environment_changes: [],
        },
      }),
    ]

    const wrapper = mount(ActionTimeline, {
      props: {
        rounds,
      },
    })

    const alerts = wrapper.findAll('.alert')
    expect(alerts.length).toBe(1)

    const item = wrapper.find('el-timeline-item')
    expect(item.exists()).toBe(true)
    await item.trigger('click')

    const emitted = wrapper.emitted('select') || []
    expect(emitted.length).toBe(1)
    expect(emitted[0]).toEqual([rounds[0]])
  })

  it('hides conflict section when there are no conflicts', () => {
    const wrapper = mount(ActionTimeline, {
      props: {
        rounds: [makeRound()],
      },
    })

    expect(wrapper.findAll('.alert').length).toBe(0)
  })
})
