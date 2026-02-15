import { apiClient } from './index'
import type { WorldEntity } from '../types/entity'

type EntityMutationResponse = Partial<WorldEntity> & { id?: string }

type RootRelationsResponse = {
  relations: Array<{ from_entity_id: string; to_entity_id: string }>
}

const createEntityRequest = (rootId: string, branchId: string, data: Record<string, unknown>) =>
  apiClient.post<EntityMutationResponse>(`/roots/${rootId}/entities`, data, {
    params: { branch_id: branchId },
  })

const listEntitiesRequest = (rootId: string, branchId: string) =>
  apiClient.get<WorldEntity[]>(`/roots/${rootId}/entities`, {
    params: { branch_id: branchId },
  })

const upsertRelationRequest = (rootId: string, branchId: string, data: Record<string, unknown>) =>
  apiClient.post(`/roots/${rootId}/relations`, data, {
    params: { branch_id: branchId },
  })

export const entityApi = {
  createEntity: createEntityRequest,
  listEntities: listEntitiesRequest,
  upsertRelation: upsertRelationRequest,
}

export const fetchEntities = (rootId: string, branchId: string): Promise<WorldEntity[]> =>
  apiClient.get<WorldEntity[]>(`/roots/${rootId}/entities`, {
    params: { branch_id: branchId },
  })

export const createEntity = (
  rootId: string,
  branchId: string,
  payload: Record<string, unknown>,
): Promise<EntityMutationResponse> =>
  apiClient.post<EntityMutationResponse>(`/roots/${rootId}/entities`, payload, {
    params: { branch_id: branchId },
  })

export const updateEntity = (
  rootId: string,
  branchId: string,
  entityId: string,
  payload: Record<string, unknown>,
): Promise<EntityMutationResponse> =>
  apiClient.put<EntityMutationResponse>(`/roots/${rootId}/entities/${entityId}`, payload, {
    params: { branch_id: branchId },
  })

export const deleteEntity = (rootId: string, branchId: string, entityId: string): Promise<EntityMutationResponse> =>
  apiClient.delete<EntityMutationResponse>(`/roots/${rootId}/entities/${entityId}`, {
    params: { branch_id: branchId },
  })

export const fetchRelations = (rootId: string, branchId: string) =>
  apiClient
    .get<RootRelationsResponse>(`/roots/${rootId}`, {
      params: { branch_id: branchId },
    })
    .then((root) => {
      const resolved = root as RootRelationsResponse
      return resolved.relations.map((relation) => ({
        source: relation.from_entity_id,
        target: relation.to_entity_id,
      }))
    })
