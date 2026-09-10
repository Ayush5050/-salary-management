/**
 * Employee form state, validation and serialisation.
 *
 * Kept out of the component so the rules can be unit-tested directly, without
 * rendering anything or simulating typing. Form validation is ordinary logic;
 * it does not need a DOM to be worth testing.
 *
 * The form works in major units — an HR Manager types `150000`, not
 * `15000000` — and converts to the minor units the API expects at the boundary.
 */

import type { EmployeeDetail, EmployeeWrite, EmploymentStatus, EmploymentType } from '../api/types'
import { majorToMinor, minorToMajor } from './money'

export interface EmployeeFormValues {
  employee_code: string
  first_name: string
  last_name: string
  email: string
  country_code: string
  department: string
  job_title: string
  level: string
  employment_type: EmploymentType
  status: EmploymentStatus
  hire_date: string
  manager_id: string
  currency_code: string
  /** Major units in the employee's own currency. */
  base_salary: number | ''
  bonus: number | ''
}

export type FormErrors = Partial<Record<keyof EmployeeFormValues, string>>

export const EMPTY_EMPLOYEE_FORM: EmployeeFormValues = {
  employee_code: '',
  first_name: '',
  last_name: '',
  email: '',
  country_code: '',
  department: '',
  job_title: '',
  level: '',
  employment_type: 'FULL_TIME',
  status: 'ACTIVE',
  hire_date: '',
  manager_id: '',
  currency_code: '',
  base_salary: '',
  bonus: '',
}

export function employeeToForm(employee: EmployeeDetail): EmployeeFormValues {
  return {
    employee_code: employee.employee_code,
    first_name: employee.first_name,
    last_name: employee.last_name,
    email: employee.email,
    country_code: employee.country_code,
    department: employee.department,
    job_title: employee.job_title,
    level: employee.level,
    employment_type: employee.employment_type,
    status: employee.status,
    hire_date: employee.hire_date,
    manager_id: employee.manager === null ? '' : String(employee.manager.id),
    currency_code: employee.currency_code,
    base_salary: minorToMajor(employee.base_salary_minor),
    bonus: minorToMajor(employee.bonus_minor),
  }
}

const REQUIRED_TEXT_FIELDS: Array<[keyof EmployeeFormValues, string]> = [
  ['employee_code', 'Employee code is required'],
  ['first_name', 'First name is required'],
  ['last_name', 'Last name is required'],
  ['country_code', 'Country is required'],
  ['department', 'Department is required'],
  ['job_title', 'Job title is required'],
  ['level', 'Level is required'],
  ['currency_code', 'Pay currency is required'],
  ['hire_date', 'Hire date is required'],
]

/** Matches the backend's own address check closely enough to catch typos here. */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmployeeForm(values: EmployeeFormValues): FormErrors {
  const errors: FormErrors = {}

  for (const [field, message] of REQUIRED_TEXT_FIELDS) {
    if (String(values[field]).trim() === '') {
      errors[field] = message
    }
  }

  if (values.email.trim() === '') {
    errors.email = 'Email is required'
  } else if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = 'That does not look like an email address'
  }

  if (values.base_salary === '') {
    errors.base_salary = 'Base salary is required'
  } else if (values.base_salary < 0) {
    errors.base_salary = 'Base salary cannot be negative'
  }

  // A bonus of zero is normal — contractors have none — so only absence and
  // negative values are errors.
  if (values.bonus !== '' && values.bonus < 0) {
    errors.bonus = 'Bonus cannot be negative'
  }

  if (values.manager_id.trim() !== '' && !/^\d+$/.test(values.manager_id.trim())) {
    errors.manager_id = 'Manager must be an employee id'
  }

  return errors
}

export function isValid(errors: FormErrors): boolean {
  return Object.keys(errors).length === 0
}

/**
 * Converts validated form values into the API request body.
 *
 * Throws rather than guessing if called with invalid values: silently coercing
 * an empty salary to zero would write a real, wrong number into the payroll.
 */
export function toEmployeeWrite(values: EmployeeFormValues): EmployeeWrite {
  if (!isValid(validateEmployeeForm(values))) {
    throw new Error('refusing to serialise an invalid employee form')
  }

  return {
    employee_code: values.employee_code.trim(),
    first_name: values.first_name.trim(),
    last_name: values.last_name.trim(),
    email: values.email.trim(),
    country_code: values.country_code.toUpperCase(),
    department: values.department,
    job_title: values.job_title.trim(),
    level: values.level,
    employment_type: values.employment_type,
    status: values.status,
    hire_date: values.hire_date,
    manager_id: values.manager_id.trim() === '' ? null : Number(values.manager_id.trim()),
    currency_code: values.currency_code.toUpperCase(),
    base_salary_minor: majorToMinor(Number(values.base_salary)),
    bonus_minor: values.bonus === '' ? 0 : majorToMinor(Number(values.bonus)),
  }
}
