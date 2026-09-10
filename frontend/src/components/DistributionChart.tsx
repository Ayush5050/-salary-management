/**
 * Headcount by salary band.
 *
 * Bands are fixed server-side rather than derived from the current selection,
 * so the axis does not move when a filter changes. A histogram whose buckets
 * rescale with the data makes two views impossible to compare — which is the
 * whole reason to look at a distribution.
 */

import { Card, Skeleton, Text, useMantineTheme } from '@mantine/core'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { SalaryBand } from '../api/types'
import { formatCount } from '../lib/money'

interface DistributionChartProps {
  bands: SalaryBand[] | undefined
  isLoading: boolean
  baseCurrency: string
}

export function DistributionChart({ bands, isLoading, baseCurrency }: DistributionChartProps) {
  const theme = useMantineTheme()

  return (
    <Card withBorder padding="md" h="100%">
      <Text fw={600}>Salary distribution</Text>
      <Text size="xs" c="dimmed" mb="md">
        Employees per total-compensation band, in {baseCurrency}
      </Text>

      {isLoading || bands === undefined ? (
        <Skeleton height={280} />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={bands} margin={{ top: 8, right: 8, bottom: 40, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              angle={-35}
              textAnchor="end"
              interval={0}
              tick={{ fontSize: 11 }}
            />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip
              formatter={(value) => [formatCount(Number(value ?? 0)), 'Employees']}
              cursor={{ fill: theme.colors.gray[1] }}
            />
            <Bar
              dataKey="headcount"
              fill={theme.colors.indigo[5]}
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
