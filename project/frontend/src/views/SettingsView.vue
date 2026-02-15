<template>
  <section class="page settings-view" data-test="settings-view-root">
    <header class="header">
      <div>
        <h1>Settings</h1>
        <p class="subtitle">Manage LLM and system preferences.</p>
      </div>
      <div class="actions">
        <button type="button" data-test="settings-reset" :disabled="apiLoading" @click="resetSettings">
          Reset
        </button>
        <button type="button" data-test="settings-save" :disabled="apiLoading" @click="saveSettings">
          Save
        </button>
      </div>
    </header>

    <ApiFeedback :loading="apiLoading" :error="apiError" />

    <section class="panel" data-test="settings-llm-config">
      <h2>LLM 配置</h2>
      <label class="field">
        <span class="label">Model</span>
        <input v-model="llmConfig.model" data-test="settings-llm-model" type="text" placeholder="model" />
      </label>
      <label class="field">
        <span class="label">Temperature</span>
        <input
          v-model.number="llmConfig.temperature"
          data-test="settings-llm-temperature"
          type="number"
          min="0"
          step="0.1"
        />
      </label>
      <label class="field">
        <span class="label">Max Tokens</span>
        <input
          v-model.number="llmConfig.max_tokens"
          data-test="settings-llm-max-tokens"
          type="number"
          min="1"
          step="1"
        />
      </label>
      <label class="field">
        <span class="label">Timeout (seconds)</span>
        <input
          v-model.number="llmConfig.timeout"
          data-test="settings-llm-timeout"
          type="number"
          min="1"
          step="1"
        />
      </label>
      <label class="field">
        <span class="label">System Instruction</span>
        <textarea
          v-model="llmConfig.system_instruction"
          data-test="settings-llm-system"
          rows="4"
          placeholder="System instruction"
        ></textarea>
      </label>
      <p class="summary" data-test="settings-llm-summary">
        Model: {{ llmConfig.model }} | Temperature: {{ llmConfig.temperature }} | Max Tokens: {{ llmConfig.max_tokens }}
        | Timeout: {{ llmConfig.timeout }}
      </p>
    </section>

    <section class="panel">
      <h2>系统设置</h2>
      <label class="field inline">
        <span class="label">Auto Save</span>
        <input v-model="systemConfig.auto_save" data-test="settings-auto-save" type="checkbox" />
      </label>
      <label class="field">
        <span class="label">UI Density</span>
        <select v-model="systemConfig.ui_density" data-test="settings-ui-density">
          <option value="comfortable">Comfortable</option>
          <option value="compact">Compact</option>
          <option value="spacious">Spacious</option>
        </select>
      </label>
    </section>

    <p v-if="saveStatus" class="status" data-test="settings-save-status">{{ saveStatus }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import ApiFeedback from '../components/ApiFeedback.vue'
import { fetchLlmSettings, saveLlmSettings, type LlmSettingsPayload } from '@/api/llm'

type LlmConfig = LlmSettingsPayload['llm_config']
type SystemConfig = LlmSettingsPayload['system_config']
type SettingsPayload = LlmSettingsPayload

const createDefaultSettings = (): SettingsPayload => ({
  llm_config: {
    model: 'gemini-1.5-pro',
    temperature: 0.7,
    max_tokens: 1024,
    timeout: 60,
    system_instruction: '',
  },
  system_config: {
    auto_save: true,
    ui_density: 'comfortable',
  },
})

const defaults = createDefaultSettings()
const llmConfig = reactive<LlmConfig>({ ...defaults.llm_config })
const systemConfig = reactive<SystemConfig>({ ...defaults.system_config })

const apiLoading = ref(false)
const apiError = ref('')
const saveStatus = ref('')

const requireValidSettings = (payload: SettingsPayload) => {
  if (!payload.llm_config || typeof payload.llm_config !== 'object') {
    throw new Error('llm_config is required')
  }
  if (!payload.system_config || typeof payload.system_config !== 'object') {
    throw new Error('system_config is required')
  }
}

const applySettings = (payload: SettingsPayload) => {
  requireValidSettings(payload)
  llmConfig.model = payload.llm_config.model
  llmConfig.temperature = payload.llm_config.temperature
  llmConfig.max_tokens = payload.llm_config.max_tokens
  llmConfig.timeout = payload.llm_config.timeout
  llmConfig.system_instruction = payload.llm_config.system_instruction
  systemConfig.auto_save = payload.system_config.auto_save
  systemConfig.ui_density = payload.system_config.ui_density
}

const validateSettings = () => {
  if (!llmConfig.model.trim()) {
    throw new Error('model is required')
  }
  if (!Number.isFinite(llmConfig.temperature)) {
    throw new Error('temperature is required')
  }
  if (!Number.isFinite(llmConfig.max_tokens) || llmConfig.max_tokens <= 0) {
    throw new Error('max_tokens is required')
  }
  if (!Number.isFinite(llmConfig.timeout) || llmConfig.timeout <= 0) {
    throw new Error('timeout is required')
  }
}

const buildPayload = (): SettingsPayload => ({
  llm_config: {
    model: llmConfig.model.trim(),
    temperature: llmConfig.temperature,
    max_tokens: llmConfig.max_tokens,
    timeout: llmConfig.timeout,
    system_instruction: llmConfig.system_instruction.trim(),
  },
  system_config: {
    auto_save: systemConfig.auto_save,
    ui_density: systemConfig.ui_density,
  },
})

const loadSettings = async () => {
  apiError.value = ''
  apiLoading.value = true
  try {
    const payload = (await fetchLlmSettings()) as SettingsPayload
    applySettings(payload)
  } finally {
    apiLoading.value = false
  }
}

const saveSettings = async () => {
  apiError.value = ''
  saveStatus.value = ''
  apiLoading.value = true
  try {
    validateSettings()
    const payload = buildPayload()
    const saved = (await saveLlmSettings(payload)) as SettingsPayload
    applySettings(saved)
    saveStatus.value = `Saved at ${new Date().toISOString()}`
  } catch (error) {
    apiError.value = error instanceof Error ? error.message : 'Failed to save settings.'
  } finally {
    apiLoading.value = false
  }
}

const resetSettings = () => {
  apiError.value = ''
  saveStatus.value = ''
  void loadSettings().catch((error) => {
    apiError.value = error instanceof Error ? error.message : 'Failed to load settings.'
  })
}

onMounted(() => {
  void loadSettings().catch((error) => {
    apiError.value = error instanceof Error ? error.message : 'Failed to load settings.'
  })
})
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.subtitle {
  margin: 4px 0 0;
  color: #6b7280;
}

.actions {
  display: flex;
  gap: 8px;
}

.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 16px;
  display: grid;
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
}

.field.inline {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  color: #6b7280;
}

input,
textarea,
select {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
}

.summary {
  margin: 0;
  color: #374151;
  font-size: 13px;
}

.status {
  color: #047857;
  font-weight: 600;
}

button {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}
</style>
