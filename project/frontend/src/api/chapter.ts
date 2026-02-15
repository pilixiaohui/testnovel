import { apiClient } from './index'
import type { ChapterReviewAction, ChapterReviewStatus } from '../types/snowflake'

export interface ChapterReviewResponse {
  id: string
  review_status: ChapterReviewStatus
}

export interface ChapterRenderResponse {
  ok: boolean
  rendered_content: string
  quality_scores: Record<string, number>
}

export const renderChapter = (chapterId: string) =>
  apiClient.post<ChapterRenderResponse>(`/chapters/${chapterId}/render`)

export const reviewChapter = (chapterId: string, status: ChapterReviewAction) =>
  apiClient.post<ChapterReviewResponse>(`/chapters/${chapterId}/review`, { status })
