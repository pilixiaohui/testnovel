<template>
  <el-card class="panel">
    <div class="controls">
      <el-button @click="emit('prev')">上一轮</el-button>
      <el-button @click="emit('next')">下一轮</el-button>
      <el-button type="primary" @click="togglePlay">{{ isPlaying ? '暂停' : '播放' }}</el-button>
    </div>
    <div class="status">
      <span>当前回合 {{ currentRound }} / {{ totalRounds }}</span>
      <el-input-number v-model="localRound" :min="1" :max="totalRounds" controls-position="right" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  currentRound: number
  totalRounds: number
  isPlaying?: boolean
}>()

const emit = defineEmits<{
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'play'): void
  (e: 'pause'): void
  (e: 'goto', value: number): void
}>()

const { currentRound, totalRounds, isPlaying } = props

const localRound = computed({
  get: () => currentRound,
  set: (value: number) => emit('goto', value),
})

const togglePlay = () => {
  if (isPlaying) {
    emit('pause')
    return
  }
  emit('play')
}
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--color-muted);
}
</style>
