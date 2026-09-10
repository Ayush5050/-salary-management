/**
 * HTTP client.
 *
 * Deliberately thin, and deliberately loud: a failed request throws an
 * {@link ApiError} carrying the status and the backend's own message. The
 * backend writes those messages to be shown to a person — "email
 * 'ada@acme.example' is already used by employee ACME-00042" — so passing them
 * straight through beats replacing them with a generic apology.
 */

const API_BASE_URL = import.meta.env['VITE_API_BASE_URL'] ?? '/api'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly code: string | null,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

interface ErrorBody {
  detail?: unknown
  error?: unknown
}

/**
 * Pulls a human-readable message out of an error response.
 *
 * FastAPI reports validation failures as a list of field errors and domain
 * failures as a plain string, so both shapes are handled rather than rendering
 * "[object Object]" at the user.
 */
function extractDetail(body: ErrorBody, status: number): string {
  const { detail } = body
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item !== 'object' || item === null) return null
        const { loc, msg } = item as { loc?: unknown; msg?: unknown }
        const field = Array.isArray(loc) ? loc[loc.length - 1] : null
        return field !== null && typeof msg === 'string' ? `${String(field)}: ${msg}` : msg
      })
      .filter((message): message is string => typeof message === 'string')
    if (messages.length > 0) {
      return messages.join('; ')
    }
  }
  return `Request failed with status ${status}`
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    let body: ErrorBody = {}
    try {
      body = (await response.json()) as ErrorBody
    } catch {
      // A non-JSON error body (a proxy timeout, say) still has a useful status.
    }
    const code = typeof body.error === 'string' ? body.error : null
    throw new ApiError(response.status, extractDetail(body, response.status), code)
  }

  return (await response.json()) as T
}

/** Appends a query string only when there is one, keeping URLs tidy. */
export function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString()
  return query === '' ? path : `${path}?${query}`
}
