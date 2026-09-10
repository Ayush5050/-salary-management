/**
 * The employee list.
 *
 * Sorting and paging are server-side: with 10,000 records the browser never
 * holds more than one page, so the table stays responsive regardless of how
 * many employees the organisation has.
 */

import { Badge, Center, Group, Pagination, Skeleton, Table, Text, UnstyledButton } from '@mantine/core'
import { IconChevronDown, IconChevronUp, IconSelector } from '@tabler/icons-react'

import type { EmployeeRow, PageMeta, SortDirection, SortField } from '../api/types'
import { formatCount, formatMoney } from '../lib/money'

interface EmployeeTableProps {
  rows: EmployeeRow[] | undefined
  meta: PageMeta | undefined
  sort: SortField
  direction: SortDirection
  onSortChange: (field: SortField) => void
  onPageChange: (page: number) => void
  onSelect: (employee: EmployeeRow) => void
  isLoading: boolean
  baseCurrency: string
}

interface Column {
  field: SortField | null
  label: string
  numeric: boolean
}

const COLUMNS: Column[] = [
  { field: 'NAME', label: 'Employee', numeric: false },
  { field: 'DEPARTMENT', label: 'Department', numeric: false },
  { field: 'LEVEL', label: 'Level', numeric: false },
  { field: 'COUNTRY', label: 'Country', numeric: false },
  { field: null, label: 'Local total comp', numeric: true },
  { field: 'TOTAL_COMP_USD', label: 'Total comp (USD)', numeric: true },
  { field: 'HIRE_DATE', label: 'Hired', numeric: false },
  { field: null, label: 'Status', numeric: false },
]

function SortIcon({ active, direction }: { active: boolean; direction: SortDirection }) {
  if (!active) {
    return <IconSelector size={14} opacity={0.4} />
  }
  return direction === 'ASC' ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />
}

export function EmployeeTable({
  rows,
  meta,
  sort,
  direction,
  onSortChange,
  onPageChange,
  onSelect,
  isLoading,
  baseCurrency,
}: EmployeeTableProps) {
  if (isLoading || rows === undefined || meta === undefined) {
    return <Skeleton height={420} />
  }

  if (rows.length === 0) {
    return (
      <Center py="xl">
        <Text c="dimmed">No employees match the current filters.</Text>
      </Center>
    )
  }

  const firstOnPage = (meta.page - 1) * meta.page_size + 1
  const lastOnPage = Math.min(meta.page * meta.page_size, meta.total)

  return (
    <>
      <Table.ScrollContainer minWidth={980}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              {COLUMNS.map((column) => (
                <Table.Th key={column.label} className={column.numeric ? 'numeric' : undefined}>
                  {column.field === null ? (
                    column.label
                  ) : (
                    <UnstyledButton
                      onClick={() => onSortChange(column.field as SortField)}
                      style={{ fontWeight: 'inherit', fontSize: 'inherit' }}
                    >
                      <Group gap={4} wrap="nowrap" justify={column.numeric ? 'flex-end' : undefined}>
                        {column.label}
                        <SortIcon active={sort === column.field} direction={direction} />
                      </Group>
                    </UnstyledButton>
                  )}
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>

          <Table.Tbody>
            {rows.map((employee) => (
              <Table.Tr
                key={employee.id}
                onClick={() => onSelect(employee)}
                style={{ cursor: 'pointer' }}
              >
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {employee.full_name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {employee.job_title} · {employee.employee_code}
                  </Text>
                </Table.Td>
                <Table.Td>{employee.department_label}</Table.Td>
                <Table.Td>{employee.level}</Table.Td>
                <Table.Td>{employee.country_name}</Table.Td>
                <Table.Td className="numeric">
                  {formatMoney(employee.total_comp_local_minor, employee.currency_code)}
                </Table.Td>
                <Table.Td className="numeric">
                  {formatMoney(employee.total_comp_usd_minor, baseCurrency)}
                </Table.Td>
                <Table.Td>{employee.hire_date}</Table.Td>
                <Table.Td>
                  <Badge
                    size="sm"
                    variant="light"
                    color={employee.status === 'ACTIVE' ? 'teal' : 'gray'}
                  >
                    {employee.status === 'ACTIVE' ? 'Active' : 'Former'}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      <Group justify="space-between" mt="md">
        <Text size="sm" c="dimmed">
          {formatCount(firstOnPage)}–{formatCount(lastOnPage)} of {formatCount(meta.total)}
        </Text>
        <Pagination
          total={meta.total_pages}
          value={meta.page}
          onChange={onPageChange}
          size="sm"
          withEdges
        />
      </Group>
    </>
  )
}
