import { describe, expect, it } from 'vitest'

import type { EmployeeDetail } from '../api/types'
import type { EmployeeFormValues } from './employeeForm'
import {
  EMPTY_EMPLOYEE_FORM,
  employeeToForm,
  isValid,
  toEmployeeWrite,
  validateEmployeeForm,
} from './employeeForm'

const COMPLETE_FORM: EmployeeFormValues = {
  employee_code: 'ACME-90001',
  first_name: 'Ada',
  last_name: 'Lovelace',
  email: 'ada.lovelace@acme.example',
  country_code: 'GB',
  department: 'ENGINEERING',
  job_title: 'Principal Engineer',
  level: 'L5',
  employment_type: 'FULL_TIME',
  status: 'ACTIVE',
  hire_date: '2024-03-01',
  manager_id: '',
  currency_code: 'GBP',
  base_salary: 150_000,
  bonus: 20_000,
}

describe('validateEmployeeForm', () => {
  it('accepts a complete form', () => {
    expect(validateEmployeeForm(COMPLETE_FORM)).toEqual({})
  })

  it('reports every missing required field at once', () => {
    const errors = validateEmployeeForm(EMPTY_EMPLOYEE_FORM)

    // Reporting all of them lets the user fix the form in one pass rather than
    // rediscovering a new error on each submit.
    expect(Object.keys(errors).length).toBeGreaterThan(5)
    expect(errors.first_name).toBeDefined()
    expect(errors.base_salary).toBeDefined()
  })

  it('rejects a malformed email', () => {
    expect(validateEmployeeForm({ ...COMPLETE_FORM, email: 'ada@' }).email).toMatch(
      /email address/,
    )
  })

  it('rejects a negative salary', () => {
    expect(
      validateEmployeeForm({ ...COMPLETE_FORM, base_salary: -1 }).base_salary,
    ).toMatch(/negative/)
  })

  it('accepts a bonus of zero, which contractors have', () => {
    expect(validateEmployeeForm({ ...COMPLETE_FORM, bonus: 0 })).toEqual({})
  })

  it('accepts an omitted bonus', () => {
    expect(validateEmployeeForm({ ...COMPLETE_FORM, bonus: '' })).toEqual({})
  })

  it('rejects a non-numeric manager id', () => {
    expect(
      validateEmployeeForm({ ...COMPLETE_FORM, manager_id: 'Ada' }).manager_id,
    ).toBeDefined()
  })

  it('treats whitespace as absence', () => {
    expect(validateEmployeeForm({ ...COMPLETE_FORM, first_name: '   ' }).first_name).toBeDefined()
  })
})

describe('toEmployeeWrite', () => {
  it('converts salary from dollars to minor units', () => {
    const body = toEmployeeWrite(COMPLETE_FORM)

    expect(body.base_salary_minor).toBe(15_000_000)
    expect(body.bonus_minor).toBe(2_000_000)
  })

  it('sends an omitted bonus as zero, not null', () => {
    expect(toEmployeeWrite({ ...COMPLETE_FORM, bonus: '' }).bonus_minor).toBe(0)
  })

  it('sends an empty manager as null rather than zero', () => {
    // Zero would be a foreign key to a non-existent employee.
    expect(toEmployeeWrite(COMPLETE_FORM).manager_id).toBeNull()
  })

  it('parses a supplied manager id', () => {
    expect(toEmployeeWrite({ ...COMPLETE_FORM, manager_id: ' 42 ' }).manager_id).toBe(42)
  })

  it('normalises codes to upper case and trims text', () => {
    const body = toEmployeeWrite({
      ...COMPLETE_FORM,
      country_code: 'gb',
      currency_code: 'gbp',
      first_name: '  Ada  ',
    })

    expect(body.country_code).toBe('GB')
    expect(body.currency_code).toBe('GBP')
    expect(body.first_name).toBe('Ada')
  })

  it('refuses to serialise an invalid form instead of coercing it', () => {
    // Coercing an empty salary to zero would write a real, wrong number into
    // the payroll.
    expect(() => toEmployeeWrite({ ...COMPLETE_FORM, base_salary: '' })).toThrow(
      /invalid employee form/,
    )
  })
})

describe('employeeToForm', () => {
  const detail: EmployeeDetail = {
    id: 1,
    employee_code: 'ACME-00001',
    first_name: 'Ada',
    last_name: 'Lovelace',
    full_name: 'Ada Lovelace',
    email: 'ada@acme.example',
    country_code: 'GB',
    country_name: 'United Kingdom',
    department: 'ENGINEERING',
    department_label: 'Engineering',
    job_title: 'Principal Engineer',
    level: 'L5',
    level_label: 'L5 · Principal',
    employment_type: 'FULL_TIME',
    employment_type_label: 'Full time',
    status: 'ACTIVE',
    hire_date: '2024-03-01',
    currency_code: 'GBP',
    currency_symbol: '£',
    base_salary_minor: 15_000_000,
    bonus_minor: 2_000_000,
    total_comp_local_minor: 17_000_000,
    total_comp_usd_minor: 21_590_000,
    manager: { id: 7, employee_code: 'ACME-00007', full_name: 'Grace Hopper' },
    created_at: '2024-03-01T00:00:00',
    updated_at: '2024-03-01T00:00:00',
  }

  it('presents stored minor units as editable major units', () => {
    expect(employeeToForm(detail).base_salary).toBe(150_000)
  })

  it('round-trips through the form without changing the stored amount', () => {
    // Editing a name must not perturb the salary by a rounding step.
    expect(toEmployeeWrite(employeeToForm(detail)).base_salary_minor).toBe(
      detail.base_salary_minor,
    )
  })

  it('carries the manager id into the form', () => {
    expect(employeeToForm(detail).manager_id).toBe('7')
  })

  it('leaves the manager blank when there is none', () => {
    expect(employeeToForm({ ...detail, manager: null }).manager_id).toBe('')
  })

  it('produces a form that validates', () => {
    expect(isValid(validateEmployeeForm(employeeToForm(detail)))).toBe(true)
  })
})
