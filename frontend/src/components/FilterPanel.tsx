/**
 * The filter panel, shared by the dashboard and the employee list.
 *
 * One component for both views, driven by one URL-backed state, so the two
 * pages cannot offer different filters or interpret them differently.
 */

import {
  Badge,
  Button,
  Card,
  Grid,
  Group,
  MultiSelect,
  NumberInput,
  TextInput,
} from '@mantine/core'
import { useDebouncedCallback } from '@mantine/hooks'
import { IconSearch, IconX } from '@tabler/icons-react'
import { useEffect, useState } from 'react'

import type { ReferenceData } from '../api/types'
import type { FilterState } from '../lib/filters'
import { DEFAULT_FILTERS, activeFilterCount, compensationRangeError } from '../lib/filters'

interface FilterPanelProps {
  filters: FilterState
  onChange: (next: FilterState) => void
  reference: ReferenceData | undefined
}

const SEARCH_DEBOUNCE_MS = 300

export function FilterPanel({ filters, onChange, reference }: FilterPanelProps) {
  // The search box keeps its own immediate state so typing stays responsive,
  // while the URL and the queries update on a debounce. Without this, every
  // keystroke would push a history entry and fire four requests.
  const [searchDraft, setSearchDraft] = useState(filters.search)

  useEffect(() => {
    setSearchDraft(filters.search)
  }, [filters.search])

  const commitSearch = useDebouncedCallback((value: string) => {
    onChange({ ...filters, search: value })
  }, SEARCH_DEBOUNCE_MS)

  const update = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    onChange({ ...filters, [key]: value })
  }

  const rangeError = compensationRangeError(filters)
  const activeCount = activeFilterCount(filters)

  const countryOptions =
    reference?.countries.map((country) => ({ value: country.code, label: country.name })) ?? []

  return (
    <Card withBorder padding="md" mb="lg">
      <Grid gap="sm" align="flex-start">
        <Grid.Col span={{ base: 12, md: 4 }}>
          <TextInput
            label="Search"
            placeholder="Name, email, employee code or job title"
            leftSection={<IconSearch size={16} />}
            value={searchDraft}
            onChange={(event) => {
              const { value } = event.currentTarget
              setSearchDraft(value)
              commitSearch(value)
            }}
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <MultiSelect
            label="Country"
            placeholder={filters.countries.length === 0 ? 'All countries' : undefined}
            data={countryOptions}
            value={filters.countries}
            onChange={(value) => update('countries', value)}
            searchable
            clearable
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <MultiSelect
            label="Department"
            placeholder={filters.departments.length === 0 ? 'All departments' : undefined}
            data={reference?.departments ?? []}
            value={filters.departments}
            onChange={(value) => update('departments', value)}
            searchable
            clearable
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <MultiSelect
            label="Level"
            placeholder={filters.levels.length === 0 ? 'All levels' : undefined}
            data={reference?.levels ?? []}
            value={filters.levels}
            onChange={(value) => update('levels', value)}
            clearable
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <MultiSelect
            label="Employment type"
            placeholder={filters.employmentTypes.length === 0 ? 'All types' : undefined}
            data={reference?.employment_types ?? []}
            value={filters.employmentTypes}
            onChange={(value) => update('employmentTypes', value)}
            clearable
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <MultiSelect
            label="Status"
            placeholder={filters.statuses.length === 0 ? 'All' : undefined}
            data={reference?.statuses ?? []}
            value={filters.statuses}
            onChange={(value) => update('statuses', value)}
            clearable
          />
        </Grid.Col>

        <Grid.Col span={{ base: 6, md: 3 }}>
          <NumberInput
            label="Min total comp"
            placeholder="USD"
            prefix="$"
            thousandSeparator
            min={0}
            step={10_000}
            value={filters.minTotalCompUsd ?? ''}
            error={rangeError !== null}
            onChange={(value) =>
              update('minTotalCompUsd', value === '' ? null : Number(value))
            }
          />
        </Grid.Col>

        <Grid.Col span={{ base: 6, md: 3 }}>
          <NumberInput
            label="Max total comp"
            placeholder="USD"
            prefix="$"
            thousandSeparator
            min={0}
            step={10_000}
            value={filters.maxTotalCompUsd ?? ''}
            error={rangeError}
            onChange={(value) =>
              update('maxTotalCompUsd', value === '' ? null : Number(value))
            }
          />
        </Grid.Col>
      </Grid>

      <Group justify="space-between" mt="md">
        <Badge variant="light" color={activeCount > 0 ? 'indigo' : 'gray'}>
          {activeCount === 0
            ? 'No filters applied'
            : `${activeCount} filter${activeCount === 1 ? '' : 's'} applied`}
        </Badge>
        <Button
          variant="subtle"
          size="compact-sm"
          leftSection={<IconX size={14} />}
          onClick={() => onChange(DEFAULT_FILTERS)}
        >
          Reset to current employees
        </Button>
      </Group>
    </Card>
  )
}
