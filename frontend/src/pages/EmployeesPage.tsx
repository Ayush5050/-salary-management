import { Alert, Button, Card, Group, Stack, Title } from '@mantine/core'
import { IconAlertTriangle, IconPlus } from '@tabler/icons-react'
import { useState } from 'react'

import { useEmployee, useEmployees, useReferenceData } from '../api/queries'
import type { SortDirection, SortField } from '../api/types'
import { EmployeeDrawer } from '../components/EmployeeDrawer'
import { EmployeeFormModal } from '../components/EmployeeFormModal'
import { EmployeeTable } from '../components/EmployeeTable'
import { FilterPanel } from '../components/FilterPanel'
import { useFilterParams } from '../hooks/useFilterParams'

const DEFAULT_PAGE_SIZE = 25

export function EmployeesPage() {
  const { filters, setFilters, apiParams, searchParams, setSearchParams } = useFilterParams()

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  // View state lives in the URL alongside the filters, so a link reproduces the
  // exact screen the sender was looking at — page and sort included.
  const sort = (searchParams.get('sort') ?? 'NAME') as SortField
  const direction = (searchParams.get('direction') ?? 'ASC') as SortDirection
  const page = Number(searchParams.get('page') ?? '1')

  const listParams = new URLSearchParams(apiParams)
  listParams.set('sort', sort)
  listParams.set('direction', direction)
  listParams.set('page', String(page))
  listParams.set('page_size', String(DEFAULT_PAGE_SIZE))

  const reference = useReferenceData()
  const employees = useEmployees(listParams)
  const editing = useEmployee(editingId)

  const baseCurrency = reference.data?.base_currency ?? 'USD'

  const updateViewParam = (updates: Record<string, string>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) {
      next.set(key, value)
    }
    setSearchParams(next)
  }

  const changeSort = (field: SortField) => {
    // Clicking the active column flips direction; a different column starts
    // ascending, which is the least surprising default for names and dates.
    const nextDirection = sort === field && direction === 'ASC' ? 'DESC' : 'ASC'
    updateViewParam({ sort: field, direction: nextDirection, page: '1' })
  }

  return (
    <Stack gap={0}>
      <Group justify="space-between" mb="md">
        <Title order={3}>Employees</Title>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => {
            setEditingId(null)
            setFormOpen(true)
          }}
        >
          Add employee
        </Button>
      </Group>

      {employees.error !== null && (
        <Alert
          color="red"
          icon={<IconAlertTriangle size={18} />}
          title="Could not load employees"
          mb="md"
        >
          {employees.error.message}
        </Alert>
      )}

      <FilterPanel filters={filters} onChange={setFilters} reference={reference.data} />

      <Card withBorder padding="md">
        <EmployeeTable
          rows={employees.data?.items}
          meta={employees.data?.meta}
          sort={sort}
          direction={direction}
          onSortChange={changeSort}
          onPageChange={(next) => updateViewParam({ page: String(next) })}
          onSelect={(employee) => setSelectedId(employee.id)}
          isLoading={employees.isPending}
          baseCurrency={baseCurrency}
        />
      </Card>

      <EmployeeDrawer
        employeeId={selectedId}
        onClose={() => setSelectedId(null)}
        onEdit={() => {
          setEditingId(selectedId)
          setSelectedId(null)
          setFormOpen(true)
        }}
        baseCurrency={baseCurrency}
      />

      <EmployeeFormModal
        opened={formOpen}
        onClose={() => {
          setFormOpen(false)
          setEditingId(null)
        }}
        employee={editingId === null ? null : (editing.data ?? null)}
        reference={reference.data}
      />
    </Stack>
  )
}
