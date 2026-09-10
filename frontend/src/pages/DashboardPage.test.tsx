/**
 * Dashboard behaviour, exercised through the real query hooks and API client
 * with only `fetch` stubbed. These assert the things a user would notice: the
 * right numbers on screen, and the filters actually reaching the backend.
 */

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { EMPTY_SUMMARY_FIXTURE, stubApi } from '../test/apiStub'
import type { ApiStub } from '../test/apiStub'
import { renderWithProviders } from '../test/renderWithProviders'
import { DashboardPage } from './DashboardPage'

describe('DashboardPage', () => {
  let api: ApiStub

  beforeEach(() => {
    api = stubApi()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows payroll spend abbreviated and headcount in full', async () => {
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    expect(
      within(screen.getByRole('group', { name: 'Annual payroll spend' })).getByText('$948.2M'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('group', { name: 'Headcount' })).getByText('9,381'),
    ).toBeInTheDocument()
  })

  it('shows average and median side by side so the skew is visible', async () => {
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Average total comp' })

    // The mean sits well above the median because senior pay is long-tailed;
    // showing only one of the two would misrepresent typical pay.
    expect(
      within(screen.getByRole('group', { name: 'Average total comp' })).getByText('$101,076'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('group', { name: 'Median total comp' })).getByText('$70,740'),
    ).toBeInTheDocument()
  })

  it('sends the URL filters to every analytics endpoint', async () => {
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE&country=IN&country=DE')

    await screen.findByRole('group', { name: 'Annual payroll spend' })

    for (const endpoint of ['/analytics/summary', '/analytics/breakdown', '/analytics/distribution']) {
      const params = api.lastRequestFor(endpoint)
      expect(params, `${endpoint} was never called`).not.toBeNull()
      expect(params?.getAll('country')).toEqual(['IN', 'DE'])
      expect(params?.getAll('status')).toEqual(['ACTIVE'])
    }
  })

  it('links to the employee list carrying the same selection', async () => {
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE&country=IN')

    const link = await screen.findByRole('link', { name: /View these 9,381 employees/ })
    const href = link.getAttribute('href') ?? ''

    // The product promise: a headline figure is one click from the people it
    // is computed from, under exactly the same filters.
    expect(href).toContain('/employees')
    expect(new URLSearchParams(href.split('?')[1]).getAll('country')).toEqual(['IN'])
  })

  it('renders a breakdown row per group, labelled by name rather than code', async () => {
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')

    expect(await screen.findByRole('link', { name: 'India' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Germany' })).toBeInTheDocument()
  })

  it('narrows the breakdown link to the row that was clicked', async () => {
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE&country=IN&country=DE')

    const germany = await screen.findByRole('link', { name: 'Germany' })
    const params = new URLSearchParams((germany.getAttribute('href') ?? '').split('?')[1])

    // Clicking one country replaces the two-country selection rather than
    // adding to it.
    expect(params.getAll('country')).toEqual(['DE'])
  })

  it('switches the breakdown dimension on request', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    await user.click(screen.getByRole('radio', { name: 'Department' }))

    await waitFor(() => {
      expect(api.lastRequestFor('/analytics/breakdown')?.get('dimension')).toBe('DEPARTMENT')
    })
  })

  it('shows a dash rather than zero when nothing matches', async () => {
    vi.unstubAllGlobals()
    stubApi({ summary: EMPTY_SUMMARY_FIXTURE })

    renderWithProviders(<DashboardPage />, '/dashboard?search=nobody')

    // "No employees matched" and "the average salary is zero" are different
    // facts and must not look alike.
    await waitFor(() => {
      expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
    })
    expect(screen.queryByRole('link', { name: /View these/ })).not.toBeInTheDocument()
  })

  it('pushes a typed search term into the query after debouncing', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    await user.type(screen.getByLabelText('Search'), 'lovelace')

    await waitFor(
      () => {
        expect(api.lastRequestFor('/analytics/summary')?.get('search')).toBe('lovelace')
      },
      { timeout: 2000 },
    )
  })
})

describe('DashboardPage · asking a question', () => {
  let api: ApiStub

  beforeEach(() => {
    api = stubApi()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows what the question was understood to mean', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    await user.type(screen.getByLabelText('Ask a question'), 'engineering in Germany{Enter}')

    // The answer arrives with its working shown, so a misread question is
    // visible rather than indistinguishable from a correct one.
    expect(
      await screen.findByText('Current employees in Engineering based in DE'),
    ).toBeInTheDocument()
  })

  it('names the words it ignored rather than dropping them silently', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    await user.type(screen.getByLabelText('Ask a question'), 'engineering on tuesdays{Enter}')

    expect(await screen.findByText(/Ignored: tuesdays/)).toBeInTheDocument()
  })

  it('re-queries the dashboard through the ordinary filter path', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    await user.type(screen.getByLabelText('Ask a question'), 'engineering in Germany{Enter}')

    // There is no separate "answered by AI" request: the question becomes the
    // URL, and the normal analytics endpoints run under it.
    await waitFor(() => {
      const params = api.lastRequestFor('/analytics/summary')
      expect(params?.getAll('country')).toEqual(['DE'])
      expect(params?.getAll('department')).toEqual(['ENGINEERING'])
    })
  })

  it('applies a grouping the question asked for', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, '/dashboard?status=ACTIVE')
    await screen.findByRole('group', { name: 'Annual payroll spend' })

    await user.type(screen.getByLabelText('Ask a question'), 'engineering by level{Enter}')

    await waitFor(() => {
      expect(api.lastRequestFor('/analytics/breakdown')?.get('dimension')).toBe('LEVEL')
    })
  })
})
