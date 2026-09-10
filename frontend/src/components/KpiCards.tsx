/**
 * The headline figures.
 *
 * Average and median sit side by side deliberately. Compensation distributions
 * are right-skewed — a handful of executives pull the mean well above what a
 * typical employee earns — so showing only one of the two would mislead. Seeing
 * them differ is itself the insight.
 */

import { Card, Group, Skeleton, Stack, Text, Tooltip } from '@mantine/core'
import { IconCoin, IconScale, IconTrendingUp, IconUsers } from '@tabler/icons-react'
import type { Icon } from '@tabler/icons-react'

import type { Stats } from '../api/types'
import { formatCompactMoney, formatCount, formatMoney, formatOptionalMoney } from '../lib/money'

interface KpiCardsProps {
  stats: Stats | undefined
  isLoading: boolean
  baseCurrency: string
}

interface Kpi {
  label: string
  value: string
  /** Shown on hover when `value` is abbreviated. */
  precise: string | null
  hint: string
  icon: Icon
}

function buildKpis(stats: Stats, baseCurrency: string): Kpi[] {
  return [
    {
      label: 'Annual payroll spend',
      value: formatCompactMoney(stats.total_usd_minor, baseCurrency),
      precise: formatMoney(stats.total_usd_minor, baseCurrency),
      hint: `Base + bonus, normalised to ${baseCurrency}`,
      icon: IconCoin,
    },
    {
      label: 'Headcount',
      value: formatCount(stats.headcount),
      precise: null,
      hint: 'Employees matching the current filters',
      icon: IconUsers,
    },
    {
      label: 'Average total comp',
      value: formatOptionalMoney(stats.average_usd_minor, baseCurrency),
      precise: null,
      hint: 'Pulled upward by the highest earners',
      icon: IconTrendingUp,
    },
    {
      label: 'Median total comp',
      value: formatOptionalMoney(stats.median_usd_minor, baseCurrency),
      precise: null,
      hint: 'What a typical employee earns',
      icon: IconScale,
    },
  ]
}

export function KpiCards({ stats, isLoading, baseCurrency }: KpiCardsProps) {
  if (isLoading || stats === undefined) {
    return (
      <Group grow align="stretch" mb="lg">
        {[0, 1, 2, 3].map((index) => (
          <Card key={index} withBorder padding="md">
            <Skeleton height={12} width="60%" mb="sm" />
            <Skeleton height={28} width="80%" />
          </Card>
        ))}
      </Group>
    )
  }

  return (
    <Group grow align="stretch" mb="lg">
      {buildKpis(stats, baseCurrency).map((kpi) => (
        // Grouped and labelled so the figure is announced with the metric it
        // belongs to, rather than as a bare number in a row of four.
        <Card key={kpi.label} withBorder padding="md" role="group" aria-label={kpi.label}>
          <Stack gap={6}>
            <Group gap={6} c="dimmed">
              <kpi.icon size={16} stroke={1.6} />
              <Text size="xs" tt="uppercase" fw={600}>
                {kpi.label}
              </Text>
            </Group>
            <Tooltip label={kpi.precise ?? kpi.hint} withArrow>
              <Text fz={28} fw={700} className="numeric" ta="left">
                {kpi.value}
              </Text>
            </Tooltip>
            <Text size="xs" c="dimmed">
              {kpi.hint}
            </Text>
          </Stack>
        </Card>
      ))}
    </Group>
  )
}
