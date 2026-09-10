/**
 * Create and edit an employee.
 *
 * One form serves both, because the fields and the rules are identical — the
 * only difference is which mutation it calls and what it starts prefilled with.
 * Two near-identical forms would be two places to update every time a field is
 * added.
 */

import {
  Alert,
  Button,
  Grid,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  TextInput,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import { useCreateEmployee, useReplaceEmployee } from '../api/queries'
import type { EmployeeDetail, ReferenceData } from '../api/types'
import type { EmployeeFormValues, FormErrors } from '../lib/employeeForm'
import {
  EMPTY_EMPLOYEE_FORM,
  employeeToForm,
  isValid,
  toEmployeeWrite,
  validateEmployeeForm,
} from '../lib/employeeForm'

interface EmployeeFormModalProps {
  opened: boolean
  onClose: () => void
  /** Null creates a new employee; a record edits that one. */
  employee: EmployeeDetail | null
  reference: ReferenceData | undefined
}

export function EmployeeFormModal({
  opened,
  onClose,
  employee,
  reference,
}: EmployeeFormModalProps) {
  const [values, setValues] = useState<EmployeeFormValues>(EMPTY_EMPLOYEE_FORM)
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  const create = useCreateEmployee()
  const replace = useReplaceEmployee(employee?.id ?? 0)
  const isEditing = employee !== null
  const isSaving = create.isPending || replace.isPending

  useEffect(() => {
    if (opened) {
      setValues(employee === null ? EMPTY_EMPLOYEE_FORM : employeeToForm(employee))
      setErrors({})
      setSubmitError(null)
    }
  }, [opened, employee])

  const update = <K extends keyof EmployeeFormValues>(key: K, value: EmployeeFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }

  /**
   * Selecting a country prefills the pay currency.
   *
   * Prefilled, not forced: an employee based in Germany may legitimately be
   * paid in USD, so the field stays editable.
   */
  const selectCountry = (code: string | null) => {
    if (code === null) return
    const country = reference?.countries.find((candidate) => candidate.code === code)
    setValues((current) => ({
      ...current,
      country_code: code,
      currency_code:
        current.currency_code === '' ? (country?.default_currency_code ?? '') : current.currency_code,
    }))
  }

  const submit = async () => {
    const validation = validateEmployeeForm(values)
    setErrors(validation)
    setSubmitError(null)
    if (!isValid(validation)) {
      return
    }

    const body = toEmployeeWrite(values)
    try {
      if (isEditing) {
        await replace.mutateAsync(body)
      } else {
        await create.mutateAsync(body)
      }
      notifications.show({
        title: isEditing ? 'Employee updated' : 'Employee added',
        message: `${body.first_name} ${body.last_name} has been saved.`,
        color: 'teal',
      })
      onClose()
    } catch (error) {
      // The backend's message names the conflicting record, which is more
      // useful than anything this component could invent.
      setSubmitError(error instanceof Error ? error.message : 'Could not save the employee')
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEditing ? `Edit ${employee.full_name}` : 'Add employee'}
      size="lg"
    >
      <Stack gap="sm">
        {submitError !== null && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />}>
            {submitError}
          </Alert>
        )}

        <Grid gap="sm">
          <Grid.Col span={6}>
            <TextInput
              label="First name"
              required
              value={values.first_name}
              error={errors.first_name}
              onChange={(e) => update('first_name', e.currentTarget.value)}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <TextInput
              label="Last name"
              required
              value={values.last_name}
              error={errors.last_name}
              onChange={(e) => update('last_name', e.currentTarget.value)}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <TextInput
              label="Employee code"
              required
              value={values.employee_code}
              error={errors.employee_code}
              onChange={(e) => update('employee_code', e.currentTarget.value)}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <TextInput
              label="Email"
              required
              value={values.email}
              error={errors.email}
              onChange={(e) => update('email', e.currentTarget.value)}
            />
          </Grid.Col>

          <Grid.Col span={6}>
            <Select
              label="Country"
              required
              searchable
              data={(reference?.countries ?? []).map((c) => ({ value: c.code, label: c.name }))}
              value={values.country_code}
              error={errors.country_code}
              onChange={selectCountry}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <Select
              label="Department"
              required
              data={reference?.departments ?? []}
              value={values.department}
              error={errors.department}
              onChange={(value) => update('department', value ?? '')}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <TextInput
              label="Job title"
              required
              value={values.job_title}
              error={errors.job_title}
              onChange={(e) => update('job_title', e.currentTarget.value)}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <Select
              label="Level"
              required
              data={reference?.levels ?? []}
              value={values.level}
              error={errors.level}
              onChange={(value) => update('level', value ?? '')}
            />
          </Grid.Col>

          <Grid.Col span={4}>
            <Select
              label="Employment type"
              data={reference?.employment_types ?? []}
              value={values.employment_type}
              onChange={(value) =>
                update('employment_type', (value ?? 'FULL_TIME') as EmployeeFormValues['employment_type'])
              }
            />
          </Grid.Col>
          <Grid.Col span={4}>
            <Select
              label="Status"
              data={reference?.statuses ?? []}
              value={values.status}
              onChange={(value) =>
                update('status', (value ?? 'ACTIVE') as EmployeeFormValues['status'])
              }
            />
          </Grid.Col>
          <Grid.Col span={4}>
            <TextInput
              label="Hire date"
              type="date"
              required
              value={values.hire_date}
              error={errors.hire_date}
              onChange={(e) => update('hire_date', e.currentTarget.value)}
            />
          </Grid.Col>

          <Grid.Col span={4}>
            <Select
              label="Pay currency"
              required
              searchable
              data={(reference?.currencies ?? []).map((c) => ({
                value: c.code,
                label: `${c.code} — ${c.name}`,
              }))}
              value={values.currency_code}
              error={errors.currency_code}
              onChange={(value) => update('currency_code', value ?? '')}
            />
          </Grid.Col>
          <Grid.Col span={4}>
            <NumberInput
              label="Base salary"
              description="Annual, in the pay currency"
              required
              min={0}
              thousandSeparator
              value={values.base_salary}
              error={errors.base_salary}
              onChange={(value) => update('base_salary', value === '' ? '' : Number(value))}
            />
          </Grid.Col>
          <Grid.Col span={4}>
            <NumberInput
              label="Bonus"
              description="Annual, in the pay currency"
              min={0}
              thousandSeparator
              value={values.bonus}
              error={errors.bonus}
              onChange={(value) => update('bonus', value === '' ? '' : Number(value))}
            />
          </Grid.Col>

          <Grid.Col span={6}>
            <TextInput
              label="Manager employee id"
              description="Optional"
              value={values.manager_id}
              error={errors.manager_id}
              onChange={(e) => update('manager_id', e.currentTarget.value)}
            />
          </Grid.Col>
        </Grid>

        <Group justify="flex-end" mt="sm">
          <Button variant="subtle" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={submit} loading={isSaving}>
            {isEditing ? 'Save changes' : 'Add employee'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
