/**
 * The record behind a row: full compensation detail, plus the two actions the
 * HR Manager can take on it.
 */

import {
  Badge,
  Button,
  Divider,
  Drawer,
  Group,
  Loader,
  Stack,
  Table,
  Text,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconEdit, IconUserOff, IconUserPlus } from '@tabler/icons-react'

import { useChangeStatus, useEmployee } from '../api/queries'
import { formatMoney } from '../lib/money'

interface EmployeeDrawerProps {
  employeeId: number | null
  onClose: () => void
  onEdit: () => void
  baseCurrency: string
}

export function EmployeeDrawer({
  employeeId,
  onClose,
  onEdit,
  baseCurrency,
}: EmployeeDrawerProps) {
  const { data: employee, isPending } = useEmployee(employeeId)
  const changeStatus = useChangeStatus(employeeId ?? 0)

  const toggleStatus = async () => {
    if (employee === undefined) return
    const next = employee.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    await changeStatus.mutateAsync(next)
    notifications.show({
      title: next === 'ACTIVE' ? 'Employee reactivated' : 'Employee deactivated',
      message:
        next === 'ACTIVE'
          ? `${employee.full_name} is back on the active roster.`
          : `${employee.full_name} is marked as a former employee. The record is kept.`,
      color: next === 'ACTIVE' ? 'teal' : 'gray',
    })
  }

  const rows =
    employee === undefined
      ? []
      : [
          ['Employee code', employee.employee_code],
          ['Email', employee.email],
          ['Job title', employee.job_title],
          ['Department', employee.department_label],
          ['Level', employee.level_label],
          ['Country', employee.country_name],
          ['Employment type', employee.employment_type_label],
          ['Hired', employee.hire_date],
          ['Manager', employee.manager?.full_name ?? '—'],
        ]

  const payRows =
    employee === undefined
      ? []
      : [
          ['Base salary', formatMoney(employee.base_salary_minor, employee.currency_code)],
          ['Bonus', formatMoney(employee.bonus_minor, employee.currency_code)],
          [
            'Total (local)',
            formatMoney(employee.total_comp_local_minor, employee.currency_code),
          ],
          [
            `Total (${baseCurrency})`,
            formatMoney(employee.total_comp_usd_minor, baseCurrency),
          ],
        ]

  return (
    <Drawer
      opened={employeeId !== null}
      onClose={onClose}
      position="right"
      size="md"
      title={
        <Group gap="sm">
          <Text fw={600}>{employee?.full_name ?? 'Employee'}</Text>
          {employee !== undefined && (
            <Badge
              size="sm"
              variant="light"
              color={employee.status === 'ACTIVE' ? 'teal' : 'gray'}
            >
              {employee.status === 'ACTIVE' ? 'Active' : 'Former'}
            </Badge>
          )}
        </Group>
      }
    >
      {isPending || employee === undefined ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : (
        <Stack gap="md">
          <Table withRowBorders={false} verticalSpacing={6}>
            <Table.Tbody>
              {rows.map(([label, value]) => (
                <Table.Tr key={label}>
                  <Table.Td c="dimmed" w="45%">
                    {label}
                  </Table.Td>
                  <Table.Td>{value}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <Divider label="Compensation" labelPosition="left" />

          <Table withRowBorders={false} verticalSpacing={6}>
            <Table.Tbody>
              {payRows.map(([label, value]) => (
                <Table.Tr key={label}>
                  <Table.Td c="dimmed" w="45%">
                    {label}
                  </Table.Td>
                  <Table.Td className="numeric" ta="left">
                    {value}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <Group mt="sm">
            <Button leftSection={<IconEdit size={16} />} onClick={onEdit}>
              Edit
            </Button>
            <Button
              variant="light"
              color={employee.status === 'ACTIVE' ? 'red' : 'teal'}
              leftSection={
                employee.status === 'ACTIVE' ? (
                  <IconUserOff size={16} />
                ) : (
                  <IconUserPlus size={16} />
                )
              }
              loading={changeStatus.isPending}
              onClick={toggleStatus}
            >
              {employee.status === 'ACTIVE' ? 'Deactivate' : 'Reactivate'}
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            Employees are never deleted. Compensation records are financial history, and a
            former employee still belongs in past payroll totals.
          </Text>
        </Stack>
      )}
    </Drawer>
  )
}
