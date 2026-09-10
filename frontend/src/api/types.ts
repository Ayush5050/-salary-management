/**
 * Wire types, mirroring the Pydantic schemas in `backend/app/schemas.py`.
 *
 * Hand-written rather than generated from the OpenAPI document. At this size
 * the generator's toolchain costs more than it saves, and hand-written types
 * carry the units in their names — `*_minor` is the reminder that a value is
 * cents, which a generator would strip to a bare `number`. The trade-off is
 * that a backend change must be mirrored here; the API tests plus TypeScript's
 * strictness make a mismatch surface as a build error rather than at runtime.
 */

export type Department = string
export type Level = string
export type EmploymentType = 'FULL_TIME' | 'PART_TIME' | 'CONTRACT'
export type EmploymentStatus = 'ACTIVE' | 'INACTIVE'
export type BreakdownDimension = 'COUNTRY' | 'DEPARTMENT' | 'LEVEL'
export type SortField =
  | 'NAME'
  | 'HIRE_DATE'
  | 'DEPARTMENT'
  | 'LEVEL'
  | 'COUNTRY'
  | 'TOTAL_COMP_USD'
export type SortDirection = 'ASC' | 'DESC'

export interface EmployeeRow {
  id: number
  employee_code: string
  first_name: string
  last_name: string
  full_name: string
  email: string
  country_code: string
  country_name: string
  department: Department
  department_label: string
  job_title: string
  level: Level
  level_label: string
  employment_type: EmploymentType
  employment_type_label: string
  status: EmploymentStatus
  hire_date: string
  currency_code: string
  currency_symbol: string
  base_salary_minor: number
  bonus_minor: number
  total_comp_local_minor: number
  total_comp_usd_minor: number
}

export interface ManagerRef {
  id: number
  employee_code: string
  full_name: string
}

export interface EmployeeDetail extends EmployeeRow {
  manager: ManagerRef | null
  created_at: string
  updated_at: string
}

export interface EmployeeWrite {
  employee_code: string
  first_name: string
  last_name: string
  email: string
  country_code: string
  department: Department
  job_title: string
  level: Level
  employment_type: EmploymentType
  status: EmploymentStatus
  hire_date: string
  manager_id: number | null
  currency_code: string
  base_salary_minor: number
  bonus_minor: number
}

export interface PageMeta {
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface EmployeeListResponse {
  items: EmployeeRow[]
  meta: PageMeta
}

/** Null everywhere but headcount and total when the selection is empty. */
export interface Stats {
  headcount: number
  total_usd_minor: number
  average_usd_minor: number | null
  median_usd_minor: number | null
  min_usd_minor: number | null
  max_usd_minor: number | null
}

export interface BreakdownGroup {
  key: string
  label: string
  stats: Stats
}

export interface SalaryBand {
  label: string
  lower_usd_minor: number
  upper_usd_minor: number | null
  headcount: number
}

export interface CountryOption {
  code: string
  name: string
  region: string
  default_currency_code: string
}

export interface CurrencyOption {
  code: string
  name: string
  symbol: string
}

export interface LabelledOption {
  value: string
  label: string
}

export interface ReferenceData {
  countries: CountryOption[]
  currencies: CurrencyOption[]
  departments: LabelledOption[]
  levels: LabelledOption[]
  employment_types: LabelledOption[]
  statuses: LabelledOption[]
  base_currency: string
}

/** What the backend understood a plain-English question to mean. */
export interface ParsedQuery {
  interpretation: string
  /** The filter query string this question means; navigate to it. */
  query_string: string
  dimension: BreakdownDimension | null
  unrecognised_terms: string[]
  understood: boolean
}
