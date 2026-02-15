import { apiClient } from './index'

type SubplotListResponse = string[]

const createSubplotRequest = (rootId: string, data: Record<string, unknown>) =>
  apiClient.post(`/roots/${rootId}/subplots`, data)

const listSubplotsRequest = (rootId: string, branchId: string): Promise<SubplotListResponse> =>
  apiClient.get<SubplotListResponse>(`/roots/${rootId}/subplots`, {
    params: { branch_id: branchId },
  })

const resolveSubplotRequest = (subplotId: string) => apiClient.post(`/subplots/${subplotId}/resolve`)

export const subplotApi = {
  createSubplot: createSubplotRequest,
  listSubplots: listSubplotsRequest,
  resolveSubplot: resolveSubplotRequest,
}

export const fetchSubplots = (rootId: string, branchId: string): Promise<SubplotListResponse> =>
  apiClient.get<SubplotListResponse>(`/roots/${rootId}/subplots`, {
    params: { branch_id: branchId },
  })
