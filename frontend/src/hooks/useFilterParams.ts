/**
 * Reads and writes the filter selection held in the URL.
 *
 * The URL is the single source of truth, so there is no local copy that could
 * drift from it. Every panel on a page derives from the same params, which is
 * the client-side half of the guarantee that the dashboard and the list agree.
 */

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { FilterState } from '../lib/filters'
import {
  DEFAULT_FILTERS,
  filtersFromSearchParams,
  filtersToSearchParams,
  mergeFiltersIntoParams,
} from '../lib/filters'

export interface FilterParams {
  filters: FilterState
  setFilters: (next: FilterState) => void
  /** The exact query string sent to the API. */
  apiParams: URLSearchParams
  searchParams: URLSearchParams
  setSearchParams: (next: URLSearchParams) => void
}

export function useFilterParams(): FilterParams {
  const [searchParams, setSearchParams] = useSearchParams()
  const hasSeededDefaults = useRef(false)

  // A first visit with a bare URL gets the sensible default — current
  // employees — written into the address bar, so the applied selection is
  // always visible and shareable rather than being an invisible assumption.
  //
  // Guarded to run at most once: without the guard, a user who deliberately
  // clears every filter would have the default silently reinstated, and the
  // "all employees, including leavers" view would be unreachable.
  useEffect(() => {
    if (hasSeededDefaults.current) {
      return
    }
    hasSeededDefaults.current = true
    if (Array.from(searchParams.keys()).length === 0) {
      setSearchParams(filtersToSearchParams(DEFAULT_FILTERS), { replace: true })
    }
  }, [searchParams, setSearchParams])

  const filters = useMemo(() => filtersFromSearchParams(searchParams), [searchParams])
  const apiParams = useMemo(() => filtersToSearchParams(filters), [filters])

  const setFilters = useCallback(
    (next: FilterState) => {
      // Changing the selection returns to the first page: staying on page 40 of
      // a result set that just shrank to three pages shows an empty table.
      const merged = mergeFiltersIntoParams(next, searchParams)
      merged.delete('page')
      setSearchParams(merged, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const replaceSearchParams = useCallback(
    (next: URLSearchParams) => setSearchParams(next, { replace: true }),
    [setSearchParams],
  )

  return { filters, setFilters, apiParams, searchParams, setSearchParams: replaceSearchParams }
}
