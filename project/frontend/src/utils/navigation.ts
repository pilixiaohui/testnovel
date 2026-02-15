import type { RouteLocationRaw } from 'vue-router'

export interface NavigationItem {
  index: string
  label: string
  description?: string
}

export type NavigationContext = {
  root_id: string
  branch_id: string
  scene_id: string
}

export const navigationItems: NavigationItem[] = [
  { index: '/', label: '首页', description: '项目概览与入口' },
  { index: '/snowflake', label: '雪花流程', description: '六步构建故事结构' },
  { index: '/simulation', label: '推演控制台', description: '回合推演与裁决' },
  { index: '/editor', label: '编辑器', description: '场景编辑与渲染' },
  { index: '/world', label: '世界观', description: '实体与锚点管理' },
  { index: '/settings', label: '设置', description: '系统配置' },
]

const routesRequiringProjectQuery = new Set(['/snowflake', '/simulation', '/editor', '/world'])

const readNonEmpty = (value: string) => {
  const normalized = value.trim()
  return normalized.length > 0 ? normalized : ''
}

export const buildNavigationTarget = (
  index: string,
  context: NavigationContext,
): RouteLocationRaw => {
  const rootId = readNonEmpty(context.root_id)
  const branchId = readNonEmpty(context.branch_id)

  if (!routesRequiringProjectQuery.has(index) || !rootId || !branchId) {
    return { path: index }
  }

  const query = {
    root_id: rootId,
    branch_id: branchId,
  }

  const sceneId = readNonEmpty(context.scene_id)
  if ((index === '/editor' || index === '/simulation') && sceneId) {
    return {
      path: `${index}/${sceneId}`,
      query,
    }
  }

  return {
    path: index,
    query,
  }
}

export const resolveActivePath = (path: string) => {
  const candidates = navigationItems
    .map((item) => item.index)
    .filter((index) => index !== '/')
    .sort((a, b) => b.length - a.length)
  const normalized = candidates.find((index) => path.startsWith(index))
  return normalized ?? path
}
