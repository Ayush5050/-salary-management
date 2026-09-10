/**
 * The client half of the shared filter model.
 *
 * Filter state lives in the URL rather than in React state, for three reasons:
 *
 * 1.  A filtered view becomes a link. "Here's what we pay engineers in Germany"
 *     is something an HR Manager sends to a colleague, and that is only
 *     possible if the selection is in the address bar.
 * 2.  Moving between the dashboard and the employee list carries the selection
 *     across for free, which is what makes "these 340 people" clickable.
 * 3.  The parameter names are exactly the ones the API accepts, so the query
 *     string is passed to the backend verbatim. There is no second mapping that
 *     could disagree with the first.
 *
 * Compensation bounds are the one exception: the UI works in whole dollars
 * because that is how people think about salary, while the API takes minor
 * units. That conversion is explicit here and nowhere else.
 */

import { majorToMinor, minorToMajor } from './money'

export interface FilterState {
  search: string
  countries: string[]
  departments: string[]
  levels: string[]
  employmentTypes: string[]
  statuses: string[]
  /** Whole USD, not minor units — this is user-facing input. */
  minTotalCompUsd: number | null
  maxTotalCompUsd: number | null
}

export const EMPTY_FILTERS: FilterState = {
  search: '',
  countries: [],
  departments: [],
  levels: [],
  employmentTypes: [],
  statuses: [],
  minTotalCompUsd: null,
  maxTotalCompUsd: null,
}

/**
 * The default view: current employees only.
 *
 * An HR Manager asking "what do we pay?" means the people on the payroll now.
 * Former employees remain in the data and are one click away, but including
 * them by default would silently inflate every headline figure.
 */
export const DEFAULT_FILTERS: FilterState = { ...EMPTY_FILTERS, statuses: ['ACTIVE'] }

const PARAM = {
  search: 'search',
  country: 'country',
  department: 'department',
  level: 'level',
  employmentType: 'employment_type',
  status: 'status',
  minComp: 'min_total_comp_usd_minor',
  maxComp: 'max_total_comp_usd_minor',
} as const

/** Parameters that belong to the view, not the selection. */
const VIEW_PARAMS = new Set(['page', 'page_size', 'sort', 'direction', 'dimension'])

function parseOptionalDollars(raw: string | null): number | null {
  if (raw === null || raw.trim() === '') {
    return null
  }
  const minorUnits = Number(raw)
  return Number.isFinite(minorUnits) ? minorToMajor(minorUnits) : null
}

export function filtersFromSearchParams(params: URLSearchParams): FilterState {
  return {
    search: params.get(PARAM.search) ?? '',
    countries: params.getAll(PARAM.country),
    departments: params.getAll(PARAM.department),
    levels: params.getAll(PARAM.level),
    employmentTypes: params.getAll(PARAM.employmentType),
    statuses: params.getAll(PARAM.status),
    minTotalCompUsd: parseOptionalDollars(params.get(PARAM.minComp)),
    maxTotalCompUsd: parseOptionalDollars(params.get(PARAM.maxComp)),
  }
}

/**
 * Serialises a selection to the query string the API accepts.
 *
 * Empty values are omitted rather than sent as blanks, which keeps shared links
 * readable and means an untouched filter contributes nothing to the request.
 */
export function filtersToSearchParams(filters: FilterState): URLSearchParams {
  const params = new URLSearchParams()

  if (filters.search.trim() !== '') {
    params.set(PARAM.search, filters.search.trim())
  }
  for (const country of filters.countries) params.append(PARAM.country, country)
  for (const department of filters.departments) params.append(PARAM.department, department)
  for (const level of filters.levels) params.append(PARAM.level, level)
  for (const type of filters.employmentTypes) params.append(PARAM.employmentType, type)
  for (const status of filters.statuses) params.append(PARAM.status, status)

  if (filters.minTotalCompUsd !== null) {
    params.set(PARAM.minComp, String(majorToMinor(filters.minTotalCompUsd)))
  }
  if (filters.maxTotalCompUsd !== null) {
    params.set(PARAM.maxComp, String(majorToMinor(filters.maxTotalCompUsd)))
  }

  return params
}

/** Merges a selection into existing params, leaving view params untouched. */
export function mergeFiltersIntoParams(
  filters: FilterState,
  existing: URLSearchParams,
): URLSearchParams {
  const merged = filtersToSearchParams(filters)
  for (const [key, value] of existing.entries()) {
    if (VIEW_PARAMS.has(key)) {
      merged.append(key, value)
    }
  }
  return merged
}

/** How many facets are narrowing the view, for the "clear filters" affordance. */
export function activeFilterCount(filters: FilterState): number {
  return [
    filters.search.trim() !== '',
    filters.countries.length > 0,
    filters.departments.length > 0,
    filters.levels.length > 0,
    filters.employmentTypes.length > 0,
    filters.statuses.length > 0,
    filters.minTotalCompUsd !== null,
    filters.maxTotalCompUsd !== null,
  ].filter(Boolean).length
}

/**
 * Whether the range is self-contradictory.
 *
 * The API rejects an inverted range with a 400, but catching it here lets the
 * form say so next to the field instead of surfacing a failed request.
 */
export function compensationRangeError(filters: FilterState): string | null {
  const { minTotalCompUsd, maxTotalCompUsd } = filters
  if (minTotalCompUsd !== null && maxTotalCompUsd !== null && minTotalCompUsd > maxTotalCompUsd) {
    return 'Minimum is above the maximum, so no one would match'
  }
  return null
}
