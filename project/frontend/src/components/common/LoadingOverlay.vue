<template>
  <transition name="fade">
    <div v-if="props.visible" :class="['overlay', { fullscreen: props.fullscreen }]">
      <div class="content">
        <el-icon class="spinner">
          <Loading />
        </el-icon>
        <span>{{ props.text }}</span>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    visible: boolean
    text?: string
    fullscreen?: boolean
  }>(),
  {
    text: '加载中...',
    fullscreen: true,
  },
)

</script>

<style scoped>
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  color: var(--color-text);
  z-index: 10;
}

.overlay.fullscreen {
  position: fixed;
  z-index: 2000;
}

.content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.spinner {
  animation: spin 1s linear infinite;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
