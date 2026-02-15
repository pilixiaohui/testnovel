import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SettingsView from '../views/SettingsView.vue'

const fetchLlmSettingsMock = vi.hoisted(() => vi.fn())
const saveLlmSettingsMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/llm', () => ({
  fetchLlmSettings: fetchLlmSettingsMock,
  saveLlmSettings: saveLlmSettingsMock,
}))

const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchLlmSettingsMock.mockResolvedValue({
      llm_config: {
        model: 'model-alpha',
        temperature: 0.5,
        max_tokens: 256,
        timeout: 45,
        system_instruction: 'focus on clarity',
      },
      system_config: {
        auto_save: false,
        ui_density: 'compact',
      },
    })
    saveLlmSettingsMock.mockResolvedValue({
      llm_config: {
        model: 'model-alpha',
        temperature: 0.5,
        max_tokens: 256,
        timeout: 45,
        system_instruction: 'focus on clarity',
      },
      system_config: {
        auto_save: false,
        ui_density: 'compact',
      },
    })
  })

  it('loads settings from backend', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(fetchLlmSettingsMock).toHaveBeenCalledTimes(1)
    expect((wrapper.get('[data-test="settings-llm-model"]').element as HTMLInputElement).value).toBe(
      'model-alpha',
    )
    expect(
      (wrapper.get('[data-test="settings-llm-temperature"]').element as HTMLInputElement).value,
    ).toBe('0.5')
    expect(
      (wrapper.get('[data-test="settings-llm-max-tokens"]').element as HTMLInputElement).value,
    ).toBe('256')
    expect(
      (wrapper.get('[data-test="settings-llm-timeout"]').element as HTMLInputElement).value,
    ).toBe('45')
    expect(
      (wrapper.get('[data-test="settings-llm-system"]').element as HTMLTextAreaElement).value,
    ).toBe('focus on clarity')
    expect(
      (wrapper.get('[data-test="settings-auto-save"]').element as HTMLInputElement).checked,
    ).toBe(false)
    expect(
      (wrapper.get('[data-test="settings-ui-density"]').element as HTMLSelectElement).value,
    ).toBe('compact')
  })

  it('saves settings through backend API and shows status', async () => {
    saveLlmSettingsMock.mockResolvedValue({
      llm_config: {
        model: 'model-beta',
        temperature: 0.9,
        max_tokens: 512,
        timeout: 30,
        system_instruction: 'system prompt',
      },
      system_config: {
        auto_save: true,
        ui_density: 'spacious',
      },
    })

    const wrapper = mount(SettingsView)
    await flushPromises()

    await wrapper.get('[data-test="settings-llm-model"]').setValue('model-beta')
    await wrapper.get('[data-test="settings-llm-temperature"]').setValue('0.9')
    await wrapper.get('[data-test="settings-llm-max-tokens"]').setValue('512')
    await wrapper.get('[data-test="settings-llm-timeout"]').setValue('30')
    await wrapper.get('[data-test="settings-llm-system"]').setValue('system prompt')
    await wrapper.get('[data-test="settings-auto-save"]').setValue(true)
    await wrapper.get('[data-test="settings-ui-density"]').setValue('spacious')

    await wrapper.get('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(saveLlmSettingsMock).toHaveBeenCalledWith({
      llm_config: {
        model: 'model-beta',
        temperature: 0.9,
        max_tokens: 512,
        timeout: 30,
        system_instruction: 'system prompt',
      },
      system_config: {
        auto_save: true,
        ui_density: 'spacious',
      },
    })

    expect(wrapper.get('[data-test="settings-save-status"]').text()).toContain('Saved')
  })

  it('shows error when model is missing', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()

    await wrapper.get('[data-test="settings-llm-model"]').setValue('')
    await wrapper.get('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="api-error"]').text()).toContain('model is required')
  })
})
