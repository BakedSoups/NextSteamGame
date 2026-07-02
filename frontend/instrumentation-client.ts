import posthog from 'posthog-js'

const posthogToken = process.env.NEXT_PUBLIC_POSTHOG_TOKEN
const posthogHost = process.env.NEXT_PUBLIC_POSTHOG_HOST

if (posthogToken && posthogHost) {
  posthog.init(posthogToken, {
    api_host: posthogHost,
    defaults: '2026-01-30',
  })
}
