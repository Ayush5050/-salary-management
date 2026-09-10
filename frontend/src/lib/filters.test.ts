import { describe, expect, it } from 'vitest'

import {
  DEFAULT_FILTERS,
  EMPTY_FILTERS,
  activeFilterCount,
  compensationRangeError,
  filtersFromSearchParams,
  filtersToSearchParams,
  mergeFiltersIntoParams,
} from './filters'

describe('parsing filters from a URL', () => {
  it('reads repeated parameters as multiple selections', () => {
    const filters = filtersFromSearchParams(
      new URLSearchParams('country=IN&country=DE&department=SALES'),
    )

    expect(filters.countries).toEqual(['IN', 'DE'])
    expect(filters.departments).toEqual(['SALES'])
  })

  it('converts compensation bounds from minor units to dollars for the UI', () => {
    const filters = filtersFromSearchParams(
      new URLSearchParams('min_total_comp_usd_minor=10000000'),
    )

    expect(filters.minTotalCompUsd).toBe(100_000)
  })

  it('treats a bare URL as no selection at all', () => {
    expect(filtersFromSearchParams(new URLSearchParams(''))).toEqual(EMPTY_FILTERS)
  })

  it('ignores a non-numeric bound instead of producing NaN', () => {
    const filters = filtersFromSearchParams(
      new URLSearchParams('min_total_comp_usd_minor=not-a-number'),
    )
    expect(filters.minTotalCompUsd).toBeNull()
  })
})

describe('serialising filters to the API query string', () => {
  it('produces exactly the parameter names the backend accepts', () => {
    const params = filtersToSearchParams({
      ...EMPTY_FILTERS,
      search: 'ada',
      countries: ['IN', 'DE'],
      departments: ['ENGINEERING'],
      statuses: ['ACTIVE'],
      minTotalCompUsd: 100_000,
    })

    expect(params.toString()).toBe(
      'search=ada&country=IN&country=DE&department=ENGINEERING&status=ACTIVE&min_total_comp_usd_minor=10000000',
    )
  })

  it('omits empty values so shared links stay readable', () => {
    expect(filtersToSearchParams(EMPTY_FILTERS).toString()).toBe('')
  })

  it('trims a padded search term', () => {
    const params = filtersToSearchParams({ ...EMPTY_FILTERS, search: '  ada  ' })
    expect(params.get('search')).toBe('ada')
  })

  it('round-trips a selection unchanged', () => {
    // The property that lets the dashboard hand its query string to the list.
    const original = {
      ...EMPTY_FILTERS,
      search: 'engineer',
      countries: ['US'],
      levels: ['L5', 'L6'],
      statuses: ['ACTIVE'],
      minTotalCompUsd: 50_000,
      maxTotalCompUsd: 250_000,
    }

    expect(filtersFromSearchParams(filtersToSearchParams(original))).toEqual(original)
  })
})

describe('merging filters with view state', () => {
  it('keeps sort and pagination while replacing the selection', () => {
    const existing = new URLSearchParams('country=IN&sort=NAME&direction=DESC&page=4')
    const merged = mergeFiltersIntoParams({ ...EMPTY_FILTERS, countries: ['DE'] }, existing)

    expect(merged.getAll('country')).toEqual(['DE'])
    expect(merged.get('sort')).toBe('NAME')
    expect(merged.get('direction')).toBe('DESC')
  })

  it('drops the old selection rather than accumulating it', () => {
    const existing = new URLSearchParams('country=IN&country=US')
    const merged = mergeFiltersIntoParams({ ...EMPTY_FILTERS, countries: ['DE'] }, existing)

    expect(merged.getAll('country')).toEqual(['DE'])
  })
})

describe('activeFilterCount', () => {
  it('counts nothing for an untouched panel', () => {
    expect(activeFilterCount(EMPTY_FILTERS)).toBe(0)
  })

  it('counts each narrowed facet once, regardless of how many values it holds', () => {
    expect(
      activeFilterCount({ ...EMPTY_FILTERS, countries: ['IN', 'DE', 'US'], search: 'ada' }),
    ).toBe(2)
  })

  it('counts the default view as one filter, since it excludes former employees', () => {
    expect(activeFilterCount(DEFAULT_FILTERS)).toBe(1)
  })
})

describe('compensationRangeError', () => {
  it('rejects an inverted range before it reaches the API', () => {
    expect(
      compensationRangeError({
        ...EMPTY_FILTERS,
        minTotalCompUsd: 200_000,
        maxTotalCompUsd: 100_000,
      }),
    ).toMatch(/no one would match/)
  })

  it('accepts an open-ended range', () => {
    expect(compensationRangeError({ ...EMPTY_FILTERS, minTotalCompUsd: 200_000 })).toBeNull()
  })

  it('accepts equal bounds', () => {
    expect(
      compensationRangeError({
        ...EMPTY_FILTERS,
        minTotalCompUsd: 100_000,
        maxTotalCompUsd: 100_000,
      }),
    ).toBeNull()
  })
})
