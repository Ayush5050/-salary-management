/**
 * Compensation broken down by country, department or level.
 *
 * Every row is a link into the employee list carrying the same filters plus the
 * row's own dimension. That is what makes an aggregate answerable: "$85.9M in
 * India" is one click from the 2,088 people it is the sum of.
 */

import { Anchor, Card, Group, SegmentedControl, Skeleton, Table, Text } from '@mantine/core'
import { Link } from 'react-router-dom'

import type { BreakdownDimension, BreakdownGroup } from '../api/types'
import { formatCount, formatMoney, formatOptionalMoney } from '../lib/money'

interface BreakdownPanelProps {
  groups: BreakdownGroup[] | undefined
  isLoading: boolean
  dimension: BreakdownDimension
  onDimensionChange: (next: BreakdownDimension) => void
  baseCurrency: string
  filterParams: URLSearchParams
}

const DIMENSION_OPTIONS = [
  { value: 'COUNTRY', label: 'Country' },
  { value: 'DEPARTMENT', label: 'Department' },
  { value: 'LEVEL', label: 'Level' },
]

/** The query parameter each dimension maps to on the employee list. */
const DIMENSION_PARAM: Record<BreakdownDimension, string> = {
  COUNTRY: 'country',
  DEPARTMENT: 'department',
  LEVEL: 'level',
}

function employeesLink(
  filterParams: URLSearchParams,
  dimension: BreakdownDimension,
  key: string,
): string {
  const params = new URLSearchParams(filterParams)
  // Replace rather than append: clicking "Germany" from a view already filtered
  // to Germany and France should show Germany, not both.
  params.delete(DIMENSION_PARAM[dimension])
  params.append(DIMENSION_PARAM[dimension], key)
  return `/employees?${params.toString()}`
}

export function BreakdownPanel({
  groups,
  isLoading,
  dimension,
  onDimensionChange,
  baseCurrency,
  filterParams,
}: BreakdownPanelProps) {
  return (
    <Card withBorder padding="md">
      <Group justify="space-between" mb="md">
        <Text fw={600}>How pay breaks down</Text>
        <SegmentedControl
          size="xs"
          value={dimension}
          onChange={(value) => onDimensionChange(value as BreakdownDimension)}
          data={DIMENSION_OPTIONS}
        />
      </Group>

      {isLoading || groups === undefined ? (
        <Skeleton height={280} />
      ) : groups.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">
          No employees match the current filters.
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{DIMENSION_OPTIONS.find((o) => o.value === dimension)?.label}</Table.Th>
                <Table.Th className="numeric">Headcount</Table.Th>
                <Table.Th className="numeric">Total spend</Table.Th>
                <Table.Th className="numeric">Average</Table.Th>
                <Table.Th className="numeric">Median</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {groups.map((group) => (
                <Table.Tr key={group.key}>
                  <Table.Td>
                    <Anchor
                      component={Link}
                      to={employeesLink(filterParams, dimension, group.key)}
                      size="sm"
                    >
                      {group.label}
                    </Anchor>
                  </Table.Td>
                  <Table.Td className="numeric">
                    {formatCount(group.stats.headcount)}
                  </Table.Td>
                  <Table.Td className="numeric">
                    {formatMoney(group.stats.total_usd_minor, baseCurrency)}
                  </Table.Td>
                  <Table.Td className="numeric">
                    {formatOptionalMoney(group.stats.average_usd_minor, baseCurrency)}
                  </Table.Td>
                  <Table.Td className="numeric">
                    {formatOptionalMoney(group.stats.median_usd_minor, baseCurrency)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Card>
  )
}
