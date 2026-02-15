import './element_plus_style_mock'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentStatePanel from '../src/components/simulation/AgentStatePanel.vue'
import type { CharacterAgentState } from '@/types/simulation'

const makeAgentState = (): CharacterAgentState => ({
  id: 'agent-1',
  character_id: 'Nova',
  branch_id: 'main',
  beliefs: {
    mood: 'focused',
    stats: { hp: 10, mp: 5 },
  },
  desires: [
    {
      id: 'd1',
      type: 'long_term',
      description: 'High priority goal',
      priority: 3,
      satisfaction_condition: 'Achieve milestone',
      created_at_scene: 1,
    },
    {
      id: 'd2',
      type: 'short_term',
      description: 'Low priority goal',
      priority: 1,
      satisfaction_condition: 'Complete task',
      created_at_scene: 1,
    },
  ],
  intentions: [
    {
      id: 'i1',
      desire_id: 'd1',
      action_type: 'investigate',
      target: 'Signal',
      expected_outcome: 'More intel',
      risk_assessment: 2,
    },
  ],
  memory: [],
  private_knowledge: {},
  last_updated_scene: 2,
  version: 1,
})

describe('AgentStatePanel', () => {
  it('renders beliefs and sorts desires by priority', () => {
    const wrapper = mount(AgentStatePanel, {
      props: {
        agentState: makeAgentState(),
      },
    })

    const listItems = wrapper.findAll('li')
    expect(listItems.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('mood')
    expect(wrapper.text()).toContain('focused')
    expect(wrapper.text()).toContain(JSON.stringify({ hp: 10, mp: 5 }))

    const desireTitles = wrapper.findAll('.desire-title').map((node) => node.text())
    expect(desireTitles[0]).toBe('High priority goal')
    expect(desireTitles[1]).toBe('Low priority goal')

    const intentionTargets = wrapper.findAll('.intention-target').map((node) => node.text())
    expect(intentionTargets[0]).toContain('Signal')
  })
})
