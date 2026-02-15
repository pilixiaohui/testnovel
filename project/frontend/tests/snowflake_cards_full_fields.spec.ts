import './element_plus_style_mock'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CharacterCard from '../src/components/snowflake/CharacterCard.vue'
import SceneCard from '../src/components/snowflake/SceneCard.vue'
import ActCard from '../src/components/snowflake/ActCard.vue'
import ChapterCard from '../src/components/snowflake/ChapterCard.vue'
import Step3Panel from '../src/components/snowflake/Step3Panel.vue'
import Step4Panel from '../src/components/snowflake/Step4Panel.vue'
import Step5Panel from '../src/components/snowflake/Step5Panel.vue'
import Step6Panel from '../src/components/snowflake/Step6Panel.vue'

describe('snowflake cards full field display', () => {
  it('renders full character fields and raw json', () => {
    const wrapper = mount(CharacterCard, {
      props: {
        character: {
          id: 'char-1',
          name: 'Hero',
          ambition: 'Save world',
          conflict: 'Inner fear',
          epiphany: 'Trust team',
          voice_dna: 'calm',
          one_sentence_summary: 'A hesitant hero learns to trust allies.',
        },
      },
    })

    expect(wrapper.text()).toContain('Save world')
    expect(wrapper.text()).toContain('Inner fear')
    expect(wrapper.text()).toContain('Trust team')
    expect(wrapper.text()).toContain('calm')
    expect(wrapper.text()).toContain('A hesitant hero learns to trust allies.')
    expect(wrapper.find('[data-test="character-card-raw"]').text()).toContain('one_sentence_summary')
  })

  it('renders full scene fields and raw json', () => {
    const wrapper = mount(SceneCard, {
      props: {
        scene: {
          id: 'scene-alpha',
          title: 'Opening',
          sequence_index: 1,
          parent_act_id: 'act-1',
          expected_outcome: 'hero leaves home',
          conflict_type: 'internal',
          actual_outcome: 'hero commits to journey',
        },
      },
    })

    expect(wrapper.text()).toContain('Opening')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('hero leaves home')
    expect(wrapper.text()).toContain('internal')
    expect(wrapper.find('[data-test="scene-card-raw"]').text()).toContain('expected_outcome')
  })

  it('renders full act/chapter fields and raw json', () => {
    const actWrapper = mount(ActCard, {
      props: {
        act: {
          id: 'act-1',
          root_id: 'root-alpha',
          sequence: 1,
          title: 'Act 1',
          purpose: 'Setup',
          tone: 'calm',
        },
      },
    })

    const chapterWrapper = mount(ChapterCard, {
      props: {
        chapter: {
          id: 'chapter-1',
          act_id: 'act-1',
          sequence: 1,
          title: 'Chapter 1',
          focus: 'Opening decision',
          pov_character_id: 'char-1',
          word_count: 2100,
        },
      },
    })

    expect(actWrapper.text()).toContain('Act 1')
    expect(actWrapper.text()).toContain('Setup')
    expect(actWrapper.text()).toContain('calm')
    expect(actWrapper.find('[data-test="act-card-raw"]').text()).toContain('purpose')

    expect(chapterWrapper.text()).toContain('Chapter 1')
    expect(chapterWrapper.text()).toContain('Opening decision')
    expect(chapterWrapper.text()).toContain('char-1')
    expect(chapterWrapper.find('[data-test="chapter-card-word-count"]').text()).toContain('2100')
    expect(chapterWrapper.find('[data-test="chapter-card-raw"]').text()).toContain('pov_character_id')
  })

  it('renders panel wrappers with full card details', () => {
    const step3Wrapper = mount(Step3Panel, {
      props: {
        characters: [
          {
            id: 'char-2',
            name: 'Lead',
            ambition: 'Win',
            conflict: 'Doubt',
            epiphany: 'Grow',
            voice_dna: 'direct',
            one_sentence_summary: 'Lead rises under pressure.',
          },
        ],
      },
    })

    const step4Wrapper = mount(Step4Panel, {
      props: {
        scenes: [
          {
            id: 'scene-2',
            title: 'Clash',
            sequence_index: 2,
            parent_act_id: 'act-2',
            expected_outcome: 'conflict escalates',
            conflict_type: 'external',
            actual_outcome: 'stalemate',
          },
        ],
      },
    })

    const step5Wrapper = mount(Step5Panel, {
      props: {
        acts: [
          {
            id: 'act-2',
            root_id: 'root-alpha',
            sequence: 2,
            title: 'Act 2',
            purpose: 'Escalation',
            tone: 'tense',
          },
        ],
        chapters: [
          {
            id: 'chapter-2',
            act_id: 'act-2',
            sequence: 2,
            title: 'Chapter 2',
            focus: 'Pressure rise',
            pov_character_id: 'char-2',
          },
        ],
      },
    })

    expect(step3Wrapper.find('[data-test="character-card-raw"]').exists()).toBe(true)
    expect(step4Wrapper.find('[data-test="scene-card-raw"]').exists()).toBe(true)
    expect(step5Wrapper.find('[data-test="act-card-raw"]').exists()).toBe(true)
    expect(step5Wrapper.find('[data-test="chapter-card-raw"]').exists()).toBe(true)
  })

  it('renders anchor required conditions, achieved status, and raw json', () => {
    const wrapper = mount(Step6Panel, {
      props: {
        anchors: [
          {
            id: 'anchor-1',
            root_id: 'root-alpha',
            branch_id: 'main',
            sequence: 1,
            anchor_type: 'midpoint',
            description: 'Hero commits to mission',
            constraint_type: 'hard',
            required_conditions: ['team assembled', 'resource secured'],
            achieved: true,
          },
        ],
      },
    })

    expect(wrapper.find('[data-test="step6-anchor-required-conditions"]').text()).toContain('team assembled')
    expect(wrapper.find('[data-test="step6-anchor-achieved"]').text()).toContain('是')
    expect(wrapper.find('[data-test="step6-anchor-raw"]').text()).toContain('required_conditions')
    expect(wrapper.find('[data-test="step6-anchor-raw"]').text()).toContain('achieved')
  })
})
