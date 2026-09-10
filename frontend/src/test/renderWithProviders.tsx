import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { RenderResult } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

/**
 * Renders a component inside the providers the real app supplies.
 *
 * Retries are off so a deliberately failing request fails immediately rather
 * than making the test wait out a backoff.
 */
export function renderWithProviders(ui: ReactNode, initialRoute: string): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    <MantineProvider>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialRoute]}>{ui}</MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  )
}
