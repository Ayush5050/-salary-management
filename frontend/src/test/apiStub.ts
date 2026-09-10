/**
 * A stub for `fetch` that answers the real API routes with canned payloads.
 *
 * Stubbing at the network boundary rather than at the module boundary means the
 * query hooks, the client, the URL building and the components all run for
 * real. A test can therefore assert what was actually requested — which is the
 * only way to catch a filter that never made it into the query string.
 */

import { vi } from 'vitest'

import type {
  BreakdownGroup,
  EmployeeListResponse,
  ParsedQuery,
  ReferenceData,
  SalaryBand,
  Stats,
} from '../api/types'

export const REFERENCE_FIXTURE: ReferenceData = {
  countries: [
    { code: 'IN', name: 'India', region: 'APAC', default_currency_code: 'INR' },
    { code: 'DE', name: 'Germany', region: 'EMEA', default_currency_code: 'EUR' },
  ],
  currencies: [
    { code: 'INR', name: 'Indian Rupee', symbol: '₹' },
    { code: 'EUR', name: 'Euro', symbol: '€' },
  ],
  departments: [{ value: 'ENGINEERING', label: 'Engineering' }],
  levels: [{ value: 'L5', label: 'L5 · Principal' }],
  employment_types: [{ value: 'FULL_TIME', label: 'Full time' }],
  statuses: [
    { value: 'ACTIVE', label: 'Active' },
    { value: 'INACTIVE', label: 'Inactive' },
  ],
  base_currency: 'USD',
}

export const SUMMARY_FIXTURE: Stats = {
  headcount: 9381,
  total_usd_minor: 94_819_348_800,
  average_usd_minor: 10_107_595,
  median_usd_minor: 7_074_000,
  min_usd_minor: 614_400,
  max_usd_minor: 88_810_000,
}

export const EMPTY_SUMMARY_FIXTURE: Stats = {
  headcount: 0,
  total_usd_minor: 0,
  average_usd_minor: null,
  median_usd_minor: null,
  min_usd_minor: null,
  max_usd_minor: null,
}

// Deliberately different figures from SUMMARY_FIXTURE, so a test asserting a
// KPI cannot accidentally be satisfied by a breakdown row showing the same
// number.
const BREAKDOWN_FIXTURE: BreakdownGroup[] = [
  {
    key: 'IN',
    label: 'India',
    stats: {
      headcount: 2088,
      total_usd_minor: 8_590_464_000,
      average_usd_minor: 4_114_200,
      median_usd_minor: 3_500_000,
      min_usd_minor: 614_400,
      max_usd_minor: 20_000_000,
    },
  },
  {
    key: 'DE',
    label: 'Germany',
    stats: {
      headcount: 903,
      total_usd_minor: 10_031_031_300,
      average_usd_minor: 11_108_600,
      median_usd_minor: 9_000_000,
      min_usd_minor: 2_000_000,
      max_usd_minor: 62_184_500,
    },
  },
]

const DISTRIBUTION_FIXTURE: SalaryBand[] = [
  { label: '< $25k', lower_usd_minor: 0, upper_usd_minor: 2_500_000, headcount: 120 },
  { label: '$300k+', lower_usd_minor: 30_000_000, upper_usd_minor: null, headcount: 8 },
]

export const EMPLOYEE_LIST_FIXTURE: EmployeeListResponse = {
  items: [
    {
      id: 1,
      employee_code: 'ACME-00001',
      first_name: 'Ada',
      last_name: 'Lovelace',
      full_name: 'Ada Lovelace',
      email: 'ada@acme.example',
      country_code: 'IN',
      country_name: 'India',
      department: 'ENGINEERING',
      department_label: 'Engineering',
      job_title: 'Principal Engineer',
      level: 'L5',
      level_label: 'L5 · Principal',
      employment_type: 'FULL_TIME',
      employment_type_label: 'Full time',
      status: 'ACTIVE',
      hire_date: '2021-06-01',
      currency_code: 'INR',
      currency_symbol: '₹',
      base_salary_minor: 250_000_000,
      bonus_minor: 25_000_000,
      total_comp_local_minor: 275_000_000,
      total_comp_usd_minor: 3_300_000,
    },
  ],
  meta: { total: 9381, page: 1, page_size: 25, total_pages: 376 },
}

export const PARSED_QUERY_FIXTURE: ParsedQuery = {
  interpretation: 'Current employees in Engineering based in DE',
  query_string: 'country=DE&department=ENGINEERING&status=ACTIVE',
  dimension: 'LEVEL',
  unrecognised_terms: ['tuesdays'],
  understood: true,
}

export interface ApiStub {
  /** Every path requested, in order, including the query string. */
  requests: string[]
  lastRequestFor: (prefix: string) => URLSearchParams | null
}

/** Installs the stub on `globalThis.fetch` and returns a record of calls. */
export function stubApi(overrides: { summary?: Stats; parsed?: ParsedQuery } = {}): ApiStub {
  const requests: string[] = []

  const respond = (body: unknown): Response =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      requests.push(url)
      const [path] = url.split('?')

      if (path?.endsWith('/reference')) return respond(REFERENCE_FIXTURE)
      if (path?.endsWith('/analytics/summary'))
        return respond(overrides.summary ?? SUMMARY_FIXTURE)
      if (path?.endsWith('/analytics/breakdown')) return respond(BREAKDOWN_FIXTURE)
      if (path?.endsWith('/analytics/distribution')) return respond(DISTRIBUTION_FIXTURE)
      if (path?.endsWith('/employees')) return respond(EMPLOYEE_LIST_FIXTURE)
      if (path?.endsWith('/query')) return respond(overrides.parsed ?? PARSED_QUERY_FIXTURE)

      throw new Error(`unstubbed request to ${url}`)
    }),
  )

  return {
    requests,
    lastRequestFor(prefix: string): URLSearchParams | null {
      const match = [...requests].reverse().find((url) => url.split('?')[0]?.endsWith(prefix))
      if (match === undefined) return null
      return new URLSearchParams(match.split('?')[1] ?? '')
    },
  }
}
