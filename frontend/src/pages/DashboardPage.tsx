import { Alert, Anchor, Grid, Group, Stack, Title } from '@mantine/core'
import { IconAlertTriangle, IconArrowRight } from '@tabler/icons-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  useBreakdown,
  useDistribution,
  useReferenceData,
  useSummary,
} from '../api/queries'
import type { BreakdownDimension } from '../api/types'
import { AskBar } from '../components/AskBar'
import { BreakdownPanel } from '../components/BreakdownPanel'
import { DistributionChart } from '../components/DistributionChart'
import { KpiCards } from '../components/KpiCards'
import { FilterPanel } from '../components/FilterPanel'
import { useFilterParams } from '../hooks/useFilterParams'
import { formatCount } from '../lib/money'

export function DashboardPage() {
  const { filters, setFilters, apiParams, setSearchParams } = useFilterParams()
  const [dimension, setDimension] = useState<BreakdownDimension>('COUNTRY')

  const reference = useReferenceData()
  const summary = useSummary(apiParams)
  const breakdown = useBreakdown(apiParams, dimension)
  const distribution = useDistribution(apiParams)

  const baseCurrency = reference.data?.base_currency ?? 'USD'
  const error = summary.error ?? breakdown.error ?? distribution.error ?? reference.error

  return (
    <Stack gap={0}>
      <Group justify="space-between" mb="md">
        <Title order={3}>How we pay people</Title>
        {summary.data !== undefined && summary.data.headcount > 0 && (
          <Anchor
            component={Link}
            // The link that makes every figure above verifiable: the same
            // selection, shown as the people it is computed from.
            to={{ pathname: '/employees', search: apiParams.toString() }}
            size="sm"
          >
            <Group gap={4}>
              View these {formatCount(summary.data.headcount)} employees
              <IconArrowRight size={14} />
            </Group>
          </Anchor>
        )}
      </Group>

      {error !== null && error !== undefined && (
        <Alert
          color="red"
          icon={<IconAlertTriangle size={18} />}
          title="Could not load the dashboard"
          mb="md"
        >
          {error.message}
        </Alert>
      )}

      <AskBar
        onApply={(queryString, askedDimension) => {
          // The question becomes the URL, so the dashboard re-renders through
          // the same filter path as the panel below it -- there is no separate
          // "answered" state that could disagree with the filters on screen.
          setSearchParams(new URLSearchParams(queryString))
          if (askedDimension !== null) {
            setDimension(askedDimension)
          }
        }}
      />

      <FilterPanel filters={filters} onChange={setFilters} reference={reference.data} />

      <KpiCards
        stats={summary.data}
        isLoading={summary.isPending}
        baseCurrency={baseCurrency}
      />

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <BreakdownPanel
            groups={breakdown.data}
            isLoading={breakdown.isPending}
            dimension={dimension}
            onDimensionChange={setDimension}
            baseCurrency={baseCurrency}
            filterParams={apiParams}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <DistributionChart
            bands={distribution.data}
            isLoading={distribution.isPending}
            baseCurrency={baseCurrency}
          />
        </Grid.Col>
      </Grid>
    </Stack>
  )
}
