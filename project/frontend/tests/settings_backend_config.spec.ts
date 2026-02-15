import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SettingsView from '../src/views/SettingsView.vue'

const fetchLlmSettingsMock = vi.hoisted(() => vi.fn())
const saveLlmSettingsMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/llm', () => ({
  fetchLlmSettings: fetchLlmSettingsMock,
  saveLlmSettings: saveLlmSettingsMock,
  llmApi: {
    toponeGenerate: vi.fn(),
    logicCheck: vi.fn(),
    stateExtract: vi.fn(),
    stateCommit: vi.fn(),
  },
}))

describe('SettingsView backend config', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchLlmSettingsMock.mockResolvedValue({
      llm_config: {
        model: 'server-model',
        temperature: 0.4,
        max_tokens: 1200,
        timeout: 45,
        system_instruction: 'server instruction',
      },
      system_config: {
        auto_save: true,
        ui_density: 'compact',
      },
    })
    saveLlmSettingsMock.mockResolvedValue({ ok: true })
  })

  it('loads LLM config from backend and saves via backend API', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(fetchLlmSettingsMock).toHaveBeenCalledTimes(1)

    const configPanel = wrapper.find('[data-test="settings-llm-config"]')
    const summary = wrapper.find('[data-test="settings-llm-summary"]')

    expect(configPanel.exists()).toBe(true)
    expect(summary.exists()).toBe(true)
    expect(summary.text()).toContain('server-model')
    expect(summary.text()).toContain('0.4')
    expect(summary.text()).toContain('1200')
    expect(summary.text()).toContain('45')

    expect((wrapper.get('[data-test="settings-llm-model"]').element as HTMLInputElement).value).toBe(
      'server-model',
    )

    await wrapper.get('[data-test="settings-llm-model"]').setValue('updated-model')
    await wrapper.get('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(saveLlmSettingsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        llm_config: expect.objectContaining({ model: 'updated-model' }),
      }),
    )
  })

  it('reloads backend config on reset', async () => {
    fetchLlmSettingsMock
      .mockResolvedValueOnce({
        llm_config: {
          model: 'server-model',
          temperature: 0.4,
          max_tokens: 1200,
          timeout: 45,
          system_instruction: 'server instruction',
        },
        system_config: {
          auto_save: true,
          ui_density: 'compact',
        },
      })
      .mockResolvedValueOnce({
        llm_config: {
          model: 'reset-model',
          temperature: 0.2,
          max_tokens: 800,
          timeout: 30,
          system_instruction: 'reset instruction',
        },
        system_config: {
          auto_save: false,
          ui_density: 'comfortable',
        },
      })

    const wrapper = mount(SettingsView)
    await flushPromises()

    await wrapper.get('[data-test="settings-reset"]').trigger('click')
    await flushPromises()

    expect(fetchLlmSettingsMock).toHaveBeenCalledTimes(2)
    expect((wrapper.get('[data-test="settings-llm-model"]').element as HTMLInputElement).value).toBe(
      'reset-model',
    )
  })
})
