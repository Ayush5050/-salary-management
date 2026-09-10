import { createTheme } from '@mantine/core'
import type { MantineThemeOverride } from '@mantine/core'

/**
 * A restrained theme.
 *
 * This is a tool someone reads numbers off for hours, so the palette stays
 * neutral and colour is reserved for meaning — status, and the accent on
 * interactive elements. Tabular figures are enabled on numeric columns so
 * digits line up vertically and a column of salaries can be scanned.
 */
export const theme: MantineThemeOverride = createTheme({
  primaryColor: 'indigo',
  defaultRadius: 'md',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  headings: { fontWeight: '650' },
  components: {
    Table: {
      defaultProps: { highlightOnHover: true, verticalSpacing: 'sm' },
    },
  },
})
