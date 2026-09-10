import '@testing-library/jest-dom/vitest'

/**
 * Mantine components measure the viewport, and jsdom implements neither
 * matchMedia nor ResizeObserver. Without these stubs any test that renders a
 * Mantine component throws before it can assert anything.
 */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
