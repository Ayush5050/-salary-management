/**
 * React Query hooks.
 *
 * Query keys are built from the serialised filter params, so the cache is keyed
 * by the exact selection. Two panels showing the same selection share one
 * request, and changing a filter invalidates precisely the queries that
 * depended on it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query'

import { apiFetch, withQuery } from './client'
import type {
  BreakdownDimension,
  BreakdownGroup,
  EmployeeDetail,
  EmployeeListResponse,
  EmployeeWrite,
  ParsedQuery,
  ReferenceData,
  SalaryBand,
  Stats,
} from './types'

const keys = {
  reference: ['reference'] as const,
  employees: (query: string) => ['employees', query] as const,
  employee: (id: number) => ['employee', id] as const,
  summary: (query: string) => ['summary', query] as const,
  breakdown: (query: string, dimension: BreakdownDimension) =>
    ['breakdown', dimension, query] as const,
  distribution: (query: string) => ['distribution', query] as const,
}

/**
 * Reference data changes with a deployment, not with the data, so it is fetched
 * once and kept for the session rather than refetched whenever a form opens.
 */
export function useReferenceData(): UseQueryResult<ReferenceData> {
  return useQuery({
    queryKey: keys.reference,
    queryFn: () => apiFetch<ReferenceData>('/reference'),
    staleTime: Infinity,
  })
}

export function useEmployees(params: URLSearchParams): UseQueryResult<EmployeeListResponse> {
  const query = params.toString()
  return useQuery({
    queryKey: keys.employees(query),
    queryFn: () => apiFetch<EmployeeListResponse>(withQuery('/employees', params)),
    // Keeping the previous page on screen while the next loads avoids the table
    // collapsing to an empty box on every page change.
    placeholderData: (previous) => previous,
  })
}

export function useEmployee(employeeId: number | null): UseQueryResult<EmployeeDetail> {
  return useQuery({
    queryKey: keys.employee(employeeId ?? 0),
    queryFn: () => apiFetch<EmployeeDetail>(`/employees/${employeeId}`),
    enabled: employeeId !== null,
  })
}

export function useSummary(params: URLSearchParams): UseQueryResult<Stats> {
  const query = params.toString()
  return useQuery({
    queryKey: keys.summary(query),
    queryFn: () => apiFetch<Stats>(withQuery('/analytics/summary', params)),
    placeholderData: (previous) => previous,
  })
}

export function useBreakdown(
  params: URLSearchParams,
  dimension: BreakdownDimension,
): UseQueryResult<BreakdownGroup[]> {
  const query = params.toString()
  return useQuery({
    queryKey: keys.breakdown(query, dimension),
    queryFn: () => {
      const withDimension = new URLSearchParams(params)
      withDimension.set('dimension', dimension)
      return apiFetch<BreakdownGroup[]>(withQuery('/analytics/breakdown', withDimension))
    },
    placeholderData: (previous) => previous,
  })
}

export function useDistribution(params: URLSearchParams): UseQueryResult<SalaryBand[]> {
  const query = params.toString()
  return useQuery({
    queryKey: keys.distribution(query),
    queryFn: () => apiFetch<SalaryBand[]>(withQuery('/analytics/distribution', params)),
    placeholderData: (previous) => previous,
  })
}

/**
 * Invalidates everything derived from employee data.
 *
 * A salary edit changes the payroll total, the medians, the band distribution
 * and the list. Invalidating broadly is correct here and cheap: these queries
 * are milliseconds, and the alternative — surgically deciding which aggregates
 * a given edit could have moved — is exactly the sort of cleverness that leaves
 * a stale number on screen.
 */
function useInvalidateEmployeeData(): () => Promise<void> {
  const queryClient = useQueryClient()
  return async () => {
    await queryClient.invalidateQueries({
      predicate: (query) => query.queryKey[0] !== 'reference',
    })
  }
}

export function useCreateEmployee(): UseMutationResult<EmployeeDetail, Error, EmployeeWrite> {
  const invalidate = useInvalidateEmployeeData()
  return useMutation({
    mutationFn: (body: EmployeeWrite) =>
      apiFetch<EmployeeDetail>('/employees', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: invalidate,
  })
}

export function useReplaceEmployee(
  employeeId: number,
): UseMutationResult<EmployeeDetail, Error, EmployeeWrite> {
  const invalidate = useInvalidateEmployeeData()
  return useMutation({
    mutationFn: (body: EmployeeWrite) =>
      apiFetch<EmployeeDetail>(`/employees/${employeeId}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: invalidate,
  })
}

export function useChangeStatus(
  employeeId: number,
): UseMutationResult<EmployeeDetail, Error, 'ACTIVE' | 'INACTIVE'> {
  const invalidate = useInvalidateEmployeeData()
  return useMutation({
    mutationFn: (status: 'ACTIVE' | 'INACTIVE') =>
      apiFetch<EmployeeDetail>(`/employees/${employeeId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    onSuccess: invalidate,
  })
}

/**
 * Translates a question into a filter selection.
 *
 * A mutation rather than a query because it is an explicit user action with no
 * cacheable identity — asking the same question twice should re-ask, not
 * silently replay a cached interpretation.
 */
export function useAskQuestion(): UseMutationResult<ParsedQuery, Error, string> {
  return useMutation({
    mutationFn: (question: string) =>
      apiFetch<ParsedQuery>('/query', { method: 'POST', body: JSON.stringify({ question }) }),
  })
}
