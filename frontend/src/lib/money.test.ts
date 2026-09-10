import { describe, expect, it } from 'vitest'

import {
  formatCompactMoney,
  formatCount,
  formatMoney,
  formatOptionalMoney,
  majorToMinor,
  minorToMajor,
} from './money'

describe('minor and major units', () => {
  it('round-trips a salary', () => {
    expect(minorToMajor(majorToMinor(124_000))).toBe(124_000)
  })

  it('rounds to the nearest minor unit rather than truncating', () => {
    expect(majorToMinor(0.005)).toBe(1)
    expect(majorToMinor(0.004)).toBe(0)
  })

  it('treats the API value as cents, not dollars', () => {
    // The mistake this module exists to prevent: rendering 15000000 as
    // $15,000,000 when it means $150,000.
    expect(minorToMajor(15_000_000)).toBe(150_000)
  })
})

describe('formatMoney', () => {
  it('formats a salary in its own currency without decimal noise', () => {
    expect(formatMoney(15_000_000, 'USD')).toBe('$150,000')
  })

  it('uses the right symbol for each currency', () => {
    expect(formatMoney(15_000_000, 'GBP')).toBe('£150,000')
    expect(formatMoney(250_000_000, 'INR')).toContain('2,500,000')
  })
})

describe('formatCompactMoney', () => {
  it('abbreviates a payroll total so the magnitude is readable at a glance', () => {
    expect(formatCompactMoney(94_819_348_800, 'USD')).toBe('$948.2M')
  })

  it('does not abbreviate an ordinary salary into uselessness', () => {
    expect(formatCompactMoney(15_000_000, 'USD')).toBe('$150K')
  })
})

describe('formatOptionalMoney', () => {
  it('renders an em dash when there is no value', () => {
    // "No employees matched" must not read as "the average salary is zero".
    expect(formatOptionalMoney(null, 'USD')).toBe('—')
  })

  it('renders a real zero as a zero', () => {
    expect(formatOptionalMoney(0, 'USD')).toBe('$0')
  })
})

describe('formatCount', () => {
  it('groups thousands', () => {
    expect(formatCount(9381)).toBe('9,381')
  })
})
