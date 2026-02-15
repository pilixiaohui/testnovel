<template>
  <section class="page home" data-test="home-view">
    <header class="hero">
      <div>
        <h1>项目概览</h1>
        <p class="subtitle">从首页进入雪花流程、推演、编辑器与世界观。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" @click="navigate('/snowflake')">开始雪花流程</el-button>
        <el-button @click="navigate('/settings')">系统设置</el-button>
      </div>
    </header>

    <ApiFeedback :loading="apiLoading" :error="apiError" />

    <el-card class="overview-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>当前项目</span>
          <el-tag size="small" type="info">Project</el-tag>
        </div>
      </template>

      <div v-if="hasProject" class="overview-content">
        <el-descriptions :column="2" size="small">
          <el-descriptions-item label="项目名称">
            <span v-if="currentProject?.name">{{ currentProject?.name }}</span>
            <el-tag v-else size="small" type="info">未设置</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="项目 ID">
            <span v-if="projectStore.root_id">{{ projectStore.root_id }}</span>
            <el-tag v-else size="small" type="info">未设置</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" type="success">进行中</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="推荐入口">雪花流程</el-descriptions-item>
        </el-descriptions>
        <div class="overview-actions">
          <el-button type="primary" @click="navigate('/editor')">进入编辑器</el-button>
          <el-button @click="navigate('/world')">世界观管理</el-button>
          <el-button @click="navigate('/simulation')">推演控制台</el-button>
        </div>
      </div>

      <div v-else class="overview-empty">
        <el-empty description="暂无项目，建议从雪花流程开始创建。" />
        <div class="overview-actions">
          <el-button type="primary" @click="navigate('/snowflake')">开始雪花流程</el-button>
        </div>
      </div>
    </el-card>

    <section class="project-section">
      <div class="section-header">
        <div class="section-title">
          <h2>项目列表</h2>
          <el-tag size="small" type="info">Roots</el-tag>
        </div>
        <div class="project-actions">
          <input
            v-model="newProjectName"
            data-test="project-create-input"
            type="text"
            placeholder="输入项目名称"
          />
          <el-button
            type="primary"
            data-test="create-project-btn"
            :disabled="isCreateDisabled"
            @click="createProject"
          >
            创建项目
          </el-button>
        </div>
      </div>
      <div
        v-if="projectStore.projects.length === 0"
        class="project-list-empty"
        data-test="project-list-empty"
      >
        <el-empty description="暂无项目，建议从雪花流程开始创建。" />
      </div>
      <div v-else class="project-list" data-test="project-list">
        <el-card
          v-for="project in projectStore.projects"
          :key="project.root_id"
          class="project-card"
          shadow="hover"
          data-test="project-card"
          @click="selectProject(project.root_id)"
        >
          <div class="project-card-title">{{ project.name }}</div>
          <div class="project-card-meta">ID: {{ project.root_id }}</div>
          <div class="project-card-meta">
            Logline:
            <span v-if="project.logline">{{ project.logline }}</span>
            <el-tag v-else size="small" type="info">未设置</el-tag>
          </div>
          <div class="project-card-meta">创建于 {{ project.created_at }}</div>
          <div class="project-card-actions">
            <el-button
              type="danger"
              size="small"
              data-test="project-delete"
              @click.stop="removeProject(project.root_id)"
            >
              删除
            </el-button>
          </div>
        </el-card>
      </div>
    </section>

    <section class="quick-section">
      <h2>快速入口</h2>
      <el-row :gutter="16">
        <el-col
          v-for="entry in quickEntries"
          :key="entry.path"
          :xs="24"
          :sm="12"
          :lg="6"
        >
          <el-card class="quick-card" shadow="hover">
            <div class="quick-body">
              <div class="quick-title">{{ entry.title }}</div>
              <p class="quick-desc">{{ entry.description }}</p>
            </div>
            <div class="quick-actions">
              <el-button type="primary" size="small" @click="navigate(entry.path)">进入</el-button>
              <el-tag size="small" type="info">{{ entry.tag }}</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../stores/project'
import ApiFeedback from '../components/ApiFeedback.vue'

const router = useRouter()
const projectStore = useProjectStore()

const apiLoading = ref(false)
const apiError = ref('')

const currentProject = computed(() =>
  projectStore.projects.find((project) => project.root_id === projectStore.root_id),
)

const hasProject = computed(() => Boolean(projectStore.root_id))

const newProjectName = ref('')
const createProjectPending = ref(false)
const isCreateDisabled = computed(
  () => newProjectName.value.trim().length === 0 || apiLoading.value || createProjectPending.value,
)

const setApiError = (error: unknown, fallback: string) => {
  apiError.value = error instanceof Error ? error.message : fallback
}

const runWithFeedback = async (action: () => Promise<void>, fallback: string) => {
  apiError.value = ''
  apiLoading.value = true
  try {
    await action()
  } catch (error) {
    setApiError(error, fallback)
  } finally {
    apiLoading.value = false
  }
}

const selectProject = async (rootId: string) => {
  await runWithFeedback(async () => {
    await projectStore.loadProject(rootId)
    await router.push('/snowflake')
  }, 'Failed to load project.')
}

const createProject = async () => {
  if (createProjectPending.value) {
    return
  }
  createProjectPending.value = true
  try {
    await runWithFeedback(async () => {
      const createdProject = await projectStore.saveProject({ name: newProjectName.value.trim() })
      await projectStore.loadProject(createdProject.root_id)
      newProjectName.value = ''
      await router.push('/snowflake')
    }, 'Failed to create project.')
  } finally {
    createProjectPending.value = false
  }
}

const removeProject = async (rootId: string) => {
  await runWithFeedback(async () => {
    await projectStore.deleteProject(rootId)
  }, 'Failed to delete project.')
}

onMounted(async () => {
  await nextTick()
  if (projectStore.projects.length === 0) {
    await runWithFeedback(async () => {
      await projectStore.listProjects()
    }, 'Failed to load projects.')
  }
})

const quickEntries = [
  {
    title: '雪花流程',
    description: '从想法到锚点，完成六步结构化设计。',
    path: '/snowflake',
    tag: 'Step 1-6',
  },
  {
    title: '推演控制台',
    description: '查看回合行动、裁决与收敛进度。',
    path: '/simulation',
    tag: 'Simulation',
  },
  {
    title: '编辑器',
    description: '编辑场景正文、渲染结果与版本。',
    path: '/editor',
    tag: 'Editor',
  },
  {
    title: '世界观',
    description: '维护实体、关系、锚点与支线。',
    path: '/world',
    tag: 'World',
  },
]

const navigate = (path: string) => {
  router.push(path)
}
</script>

<style scoped>
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.subtitle {
  margin-top: 6px;
  color: var(--color-muted);
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.overview-card {
  border-radius: var(--radius-base);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.overview-content {
  display: grid;
  gap: 16px;
}

.overview-empty {
  display: grid;
  gap: 12px;
}

.overview-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.project-section {
  display: grid;
  gap: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.project-actions input {
  min-width: 200px;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
}

.project-list {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.project-card {
  cursor: pointer;
}

.project-card-title {
  font-weight: 600;
  font-size: 16px;
}

.project-card-meta {
  margin-top: 6px;
  color: var(--color-muted);
  font-size: 12px;
}

.project-card-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.quick-section h2 {
  font-size: 18px;
}

.quick-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.quick-body {
  display: grid;
  gap: 8px;
}

.quick-title {
  font-weight: 600;
  font-size: 16px;
}

.quick-desc {
  margin: 0;
  color: var(--color-muted);
}

.quick-actions {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

@media (max-width: 768px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
