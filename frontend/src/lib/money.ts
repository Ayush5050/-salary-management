/**
 * Money formatting.
 *
 * The API sends every monetary value as an integer count of minor units, so
 * these helpers are the only place the division by 100 happens. Keeping it in
 * one module means a component can never accidentally render raw cents as
 * dollars — a mistake that is invisible in a code review and obvious to the
 * user only if they happen to know the right answer.
 */

const MINOR_UNITS_PER_MAJOR = 100

export function minorToMajor(minorUnits: number): number {
  return minorUnits / MINOR_UNITS_PER_MAJOR
}

export function majorToMinor(majorUnits: number): number {
  return Math.round(majorUnits * MINOR_UNITS_PER_MAJOR)
}

/**
 * A precise amount, e.g. `$124,000` or `¥7,300,000`.
 *
 * Annual salaries are shown without decimal places. Cents are never meaningful
 * at this magnitude, and dropping them keeps a column of figures scannable —
 * the point of the table is comparing people, not auditing pennies. The
 * underlying value keeps full precision; only the display rounds.
 */
export function formatMoney(minorUnits: number, currencyCode: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(minorToMajor(minorUnits))
}

/**
 * A compact amount for headline figures, e.g. `$948.2M`.
 *
 * Payroll totals run to hundreds of millions. Rendering those in full defeats
 * the purpose of a KPI card: the reader has to count digits to tell $94,819,348
 * from $948,193,488. The precise value stays available in a tooltip.
 */
export function formatCompactMoney(minorUnits: number, currencyCode: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(minorToMajor(minorUnits))
}

/**
 * Formats a value that may be absent.
 *
 * The API returns null for the average and median of an empty selection,
 * because "nobody matched" is not the same fact as "the average is zero". An
 * em dash carries that distinction to the screen.
 */
export function formatOptionalMoney(
  minorUnits: number | null,
  currencyCode: string,
): string {
  if (minorUnits === null) {
    return '—'
  }
  return formatMoney(minorUnits, currencyCode)
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}
