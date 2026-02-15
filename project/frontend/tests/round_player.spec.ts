import './element_plus_style_mock'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RoundPlayer from '../src/components/simulation/RoundPlayer.vue'

const mountPlayer = (isPlaying = false) =>
  mount(RoundPlayer, {
    props: {
      currentRound: 2,
      totalRounds: 6,
      isPlaying,
    },
    global: {
      stubs: {
        'el-input-number': {
          template: '<input data-test="round-input" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
        },
      },
    },
  })

describe('RoundPlayer', () => {
  it('emits prev and next events', async () => {
    const wrapper = mountPlayer()
    const buttons = wrapper.findAll('el-button')
    const prevButton = buttons.find((button) => button.text().includes('上一轮'))
    const nextButton = buttons.find((button) => button.text().includes('下一轮'))

    expect(prevButton).toBeDefined()
    expect(nextButton).toBeDefined()

    await prevButton!.trigger('click')
    await nextButton!.trigger('click')

    expect(wrapper.emitted('prev')?.length).toBe(1)
    expect(wrapper.emitted('next')?.length).toBe(1)
  })

  it('emits play when not playing', async () => {
    const wrapper = mountPlayer(false)
    const buttons = wrapper.findAll('el-button')
    const playButton = buttons.find((button) => button.text().includes('播放'))

    expect(playButton).toBeDefined()

    await playButton!.trigger('click')

    expect(wrapper.emitted('play')?.length).toBe(1)
    expect(wrapper.emitted('pause')?.length ?? 0).toBe(0)
  })

  it('emits pause when playing', async () => {
    const wrapper = mountPlayer(true)
    const buttons = wrapper.findAll('el-button')
    const pauseButton = buttons.find((button) => button.text().includes('暂停'))

    expect(pauseButton).toBeDefined()

    await pauseButton!.trigger('click')

    expect(wrapper.emitted('pause')?.length).toBe(1)
    expect(wrapper.emitted('play')?.length ?? 0).toBe(0)
  })

  it('emits goto when round input changes', async () => {
    const wrapper = mountPlayer()

    const input = wrapper.find('[data-test="round-input"]')
    expect(input.exists()).toBe(true)

    await input.setValue('5')

    expect(wrapper.emitted('goto')?.length).toBe(1)
    expect(wrapper.emitted('goto')?.[0]).toEqual([5])
  })
})
