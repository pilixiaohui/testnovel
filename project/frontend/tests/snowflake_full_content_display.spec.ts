import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/project'
import { useSnowflakeStore } from '@/stores/snowflake'
import SnowflakeView from '../src/views/SnowflakeView.vue'

const routeState = vi.hoisted(() => ({
  params: {},
  query: {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('@/api/snowflake', () => ({
  fetchSnowflakeStep1: vi.fn(),
  fetchSnowflakeStep2: vi.fn(),
  fetchSnowflakeStep3: vi.fn(),
  fetchSnowflakeStep4: vi.fn(),
  fetchSnowflakeStep5: vi.fn(),
  fetchSnowflakeStep6: vi.fn(),
  fetchSnowflakePrompts: vi.fn(),
  saveSnowflakePrompts: vi.fn(),
  resetSnowflakePrompts: vi.fn(),
  saveSnowflakeStep: vi.fn(),
  snowflakeApi: {
    listActs: vi.fn(),
    listChapters: vi.fn(),
  },
  updateSnowflakeLogline: vi.fn(),
  updateSnowflakeCharacter: vi.fn(),
  updateSnowflakeAct: vi.fn(),
  updateSnowflakeChapter: vi.fn(),
  updateSnowflakeScene: vi.fn(),
}))

const seedSnowflakeStore = () => {
  const store = useSnowflakeStore()
  store.id = 'root-alpha'
  store.steps.logline = ['logline']
  store.steps.root = {
    logline: 'logline',
    theme: 'theme',
    ending: 'ending',
    three_disasters: ['d1', 'd2', 'd3'],
  }
  store.steps.characters = [
    {
      id: 'char-1',
      name: 'Hero',
      ambition: 'Save world',
      conflict: 'Inner fear',
      epiphany: 'Trust team',
      voice_dna: 'calm',
      one_sentence_summary: 'A hesitant hero learns to trust allies.',
    },
  ]
  store.steps.scenes = [
    {
      id: 'scene-alpha',
      title: 'Opening',
      sequence_index: 1,
      parent_act_id: 'act-1',
      expected_outcome: 'hero leaves home',
      conflict_type: 'internal',
      actual_outcome: '',
      branch_id: 'main',
      is_dirty: false,
    } as unknown as (typeof store.steps.scenes)[number],
  ]
  store.steps.acts = [
    {
      id: 'act-1',
      root_id: 'root-alpha',
      sequence: 1,
      title: 'Act 1',
      purpose: 'Setup',
      tone: 'calm',
    },
  ]
  store.steps.chapters = [
    {
      id: 'chapter-1',
      act_id: 'act-1',
      sequence: 1,
      title: 'Chapter 1',
      focus: 'Start',
      pov_character_id: 'char-1',
      word_count: 1800,
    },
  ]
  store.steps.anchors = [
    {
      anchor_type: 'midpoint',
      description: 'Hero commits to the mission',
      constraint_type: 'hard',
      required_conditions: ['team assembled', 'resource secured'],
      achieved: true,
    },
  ]
  return store
}

describe('SnowflakeView full content display', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.params = {}
    routeState.query = {}
  })

  it('shows full details for character, scene, act, chapter, and anchors', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const projectStore = useProjectStore()
    projectStore.setCurrentProject('root-alpha', 'main', '')
    const store = seedSnowflakeStore()
    vi.spyOn(store, 'loadProgress').mockResolvedValue({ step: 5 })

    const wrapper = mount(SnowflakeView, {
      global: {
        plugins: [pinia],
        stubs: {
          StateExtractPanel: true,
        },
      },
    })

    await flushPromises()

    const characterDetails = wrapper.find('[data-test="snowflake-character-details"]')
    const sceneDetails = wrapper.find('[data-test="snowflake-scene-details"]')
    const actDetails = wrapper.find('[data-test="snowflake-act-details"]')
    const chapterDetails = wrapper.find('[data-test="snowflake-chapter-details"]')
    const anchorDetails = wrapper.find('[data-test="snowflake-anchor-details"]')

    const step3Details = wrapper.find('[data-test="step3-character-details"]')
    const step4Details = wrapper.find('[data-test="step4-scene-details"]')
    const step5Details = wrapper.find('[data-test="step5-act-chapter-details"]')
    const step6Details = wrapper.find('[data-test="step6-anchor-details"]')

    expect(characterDetails.exists()).toBe(true)
    expect(sceneDetails.exists()).toBe(true)
    expect(actDetails.exists()).toBe(true)
    expect(chapterDetails.exists()).toBe(true)
    expect(anchorDetails.exists()).toBe(true)

    expect(step3Details.exists()).toBe(true)
    expect(step4Details.exists()).toBe(true)
    expect(step5Details.exists()).toBe(true)
    expect(step6Details.exists()).toBe(true)

    const step1Raw = wrapper.find('[data-test="snowflake-step1-raw"]')
    const step5Raw = wrapper.find('[data-test="snowflake-step5-raw"]')
    expect(step1Raw.exists()).toBe(true)
    expect(step5Raw.exists()).toBe(true)
    expect(step1Raw.text()).toContain('logline')
    expect(step5Raw.text()).toContain('Act 1')

    expect(wrapper.find('[data-test="snowflake-character-ambition"]').text()).toContain('Save world')
    expect(wrapper.find('[data-test="snowflake-character-conflict"]').text()).toContain('Inner fear')
    expect(wrapper.find('[data-test="snowflake-character-epiphany"]').text()).toContain('Trust team')
    expect(wrapper.find('[data-test="snowflake-character-voice-dna"]').text()).toContain('calm')
    expect(wrapper.find('[data-test="snowflake-character-summary"]').text()).toContain(
      'A hesitant hero learns to trust allies.',
    )

    expect(wrapper.find('[data-test="character-ambition"]').text()).toContain('Save world')
    expect(wrapper.find('[data-test="character-conflict"]').text()).toContain('Inner fear')
    expect(wrapper.find('[data-test="character-epiphany"]').text()).toContain('Trust team')
    expect(wrapper.find('[data-test="character-voice-dna"]').text()).toContain('calm')

    expect(wrapper.find('[data-test="snowflake-scene-expected-outcome"]').text()).toContain('hero leaves home')
    expect(wrapper.find('[data-test="snowflake-scene-conflict-type"]').text()).toContain('internal')
    expect(wrapper.find('[data-test="snowflake-scene-sequence-index"]').text()).toContain('1')

    expect(wrapper.find('[data-test="snowflake-act-purpose"]').text()).toContain('Setup')
    expect(wrapper.find('[data-test="snowflake-act-tone"]').text()).toContain('calm')

    expect(wrapper.find('[data-test="snowflake-chapter-focus"]').text()).toContain('Start')
    expect(wrapper.find('[data-test="snowflake-chapter-pov"]').text()).toContain('char-1')
    expect(wrapper.find('[data-test="snowflake-chapter-word-count"]').text()).toContain('1800')

    expect(wrapper.find('[data-test="snowflake-anchor-type"]').text()).toContain('midpoint')
    expect(wrapper.find('[data-test="snowflake-anchor-description"]').text()).toContain('Hero commits to the mission')
    expect(wrapper.find('[data-test="snowflake-anchor-constraint"]').text()).toContain('hard')
    expect(wrapper.find('[data-test="snowflake-anchor-conditions"]').text()).toContain('team assembled')
    expect(wrapper.find('[data-test="snowflake-anchor-achieved"]').text()).toContain('是')
    expect(anchorDetails.text()).toContain('required_conditions')
    expect(anchorDetails.text()).toContain('achieved')
  })
})
