<template>
  <el-card class="card" data-test="character-card">
    <div class="header" data-test="character-card-name">{{ character.name }}</div>
    <div class="body">
      <p data-test="character-card-ambition">野心：{{ character.ambition }}</p>
      <p data-test="character-card-conflict">冲突：{{ character.conflict }}</p>
      <p data-test="character-card-epiphany">顿悟：{{ character.epiphany }}</p>
      <p data-test="character-card-voice-dna">声线 DNA：{{ character.voice_dna }}</p>
      <p data-test="character-card-summary">一句话总结：{{ character.one_sentence_summary || '' }}</p>
    </div>
    <pre class="raw" data-test="character-card-raw">{{ JSON.stringify(character, null, 2) }}</pre>
  </el-card>
</template>

<script setup lang="ts">
import type { CharacterSheet } from '../../types/snowflake'

const props = defineProps<{
  character: CharacterSheet
}>()

const { character } = props
</script>

<style scoped>
.card {
  display: grid;
  gap: 8px;
}

.header {
  font-weight: 600;
}

.body {
  color: var(--color-muted);
  font-size: 13px;
  display: grid;
  gap: 4px;
}

.body p {
  margin: 0;
}

.raw {
  margin: 0;
  padding: 8px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
