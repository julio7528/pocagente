# Phase 12.10 — Security Dashboard

## Ownership and read API

The dashboard represents `audit.security_events`, whose current physical
fields include `occurred_at`, `event_type`, `source_component`, nullable
`user_identifier`, request/resource categories, sanitized content, action,
result, and review state. Existing AUDIT constraints restrict event types,
source component nonblank, action/result/status vocabularies, and resource
categories. No unsupported category is invented by the dashboard.

Django MUST NOT query `audit.security_events` directly, define a duplicate
AUDIT repository, or create SQL filters over that schema. Phase 12.10 owns the
authenticated FastAPI internal administrative read boundary over the existing
AuditRepository/Application service. The only approved endpoints are:

- `GET /internal/admin/audit/summary` — totals for a validated filter;
- `GET /internal/admin/audit/timeseries` — daily event counts;
- `GET /internal/admin/audit/breakdowns` — event type, source component, and
  user aggregates under the same filter;
- `GET /internal/admin/audit/events` — bounded, cursor/page-limited sanitized
  event rows;
- `GET /internal/admin/audit/events/{event_id}` — one sanitized detail record.

All endpoints require the existing Bearer service authentication followed by
trusted `ADMIN` identity and `X-Ops-Authorized: false`. `CLIENT`,
`SUPPORT_AGENT`, missing role, and ADMIN with OPS authorization are denied.
They are not browser APIs. FastAPI validates dates, enum values, bounded
source/user filters, page, and page size; uses parameterized repository
queries; returns explicit typed DTOs; and never returns SQL, secrets, raw
input, prompts, credentials, or internal diagnostics. Event
`sanitized_content` is passed through the existing deterministic AUDIT
sanitizer before output. User breakdown includes only non-null recorded
`user_identifier` values; no portal user join or identity enrichment is made.

One canonical filter model is shared by summary, time series, breakdowns, and
event listing. Its rules are:

- `date_from` and `date_to` are ISO calendar dates interpreted in UTC. Bounds
  are inclusive dates, queried as `occurred_at >= 00:00:00 UTC` on the start
  date and `< 00:00:00 UTC` on the day after the end date.
- If both dates are omitted, use the last 30 UTC calendar days including
  today. If one is omitted, derive a 30-day window ending at the supplied
  bound or today. A reversed range or inclusive span above 90 days is 422.
- `event_type` must be one of the physical model's approved values.
  `source_component` and `user_identifier` are trimmed, nonblank when present,
  and limited to 128 characters; no arbitrary category is introduced.
- Event list defaults to page 1 and 25 rows; `page` is 1–1000 and `page_size`
  is 1–100. Rows are stably ordered by `occurred_at DESC, event_id DESC`.

Summary returns `total_events`, `distinct_users` (non-null identifiers only),
`distinct_event_types`, and `distinct_source_components` for the canonical
filter. Time series groups by UTC calendar day, is ascending, and is zero
filled in the bounded 30–90-day interval. Event-type/source breakdowns each
cover all filtered rows; user breakdown omits null identifiers, so its sum is
the number of filtered rows with a recorded user identifier.

The event list allowlists event id/time/type/source/user/resource category,
action, result, and review status. Detail may additionally return request
reference, sanitized content, reviewed time, and creation time. It omits
review notes and every raw request/prompt/provider field. The API is
read-only; it does not create events or update review state.

The existing AuditRepository currently supports event lookup, request-reference
listing, unreviewed listing, and review metadata update; aggregate/filter/list
operations needed by this dashboard are Phase 12.10 additions within that same
repository ownership boundary. Use current AUDIT indexes (`occurred_at`,
`event_type + occurred_at`, request reference, unreviewed date) first. Benchmark
the stated dashboard queries before requesting any new index or schema change.

## Dashboard behavior

Provide cards for total events, distinct users, event types, and source
components; UTC time-series counts; event-type, source-component, and
non-null-user breakdowns; and a paginated event list/detail. Django exposes
`GET /admin-portal/security/` and the same-origin
`GET /admin-portal/security/data/`; its typed server-only client calls only
the internal endpoints above. All four dashboard requests receive the same
explicit normalized date/type/source/user filters. Chart clicks set the
corresponding canonical filter and refresh every dashboard component; reset
returns to the default bounded period. Chart.js 4.5.1 is pinned and
self-hosted from its published UMD distribution and license; runtime public
CDN access is not required. Charts have accessible textual table alternatives.
Empty and API-unavailable states are explicit and safe.

## Requirements

- **REQ-P12-AUDITUI-001:** The security dashboard MUST be derived only from
  `audit.security_events` through FastAPI's existing AUDIT application and
  AuditRepository ownership boundary.
- **REQ-P12-AUDITUI-002:** Django MUST NOT directly query AUDIT, create a
  second AUDIT repository, or expose AUDIT data through an anonymous/browser
  API; reads require trusted server-to-server auth and ADMIN authorization.
- **REQ-P12-AUDITUI-003:** FastAPI MUST provide typed, bounded internal
  contracts for summary, daily time series, event-type/source/user breakdowns,
  filtered paginated event listing, and safe event detail.
- **REQ-P12-AUDITUI-004:** Dashboard filters MUST support permitted date/range,
  event type, source component, and user identifier dimensions and apply
  consistently to cards, charts, and event rows.
- **REQ-P12-AUDITUI-005:** Dashboard calculations MUST accurately report
  event totals per day, users involved, events per user, event-type
  distribution, and source-component distribution for the selected filters.
- **REQ-P12-AUDITUI-006:** Responses MUST use only physical AUDIT fields and
  approved enum values, sanitize/allowlist detail content, bound date spans
  and pagination, and omit secrets, raw request payloads, SQL, and diagnostics.
- **REQ-P12-AUDITUI-007:** The ADMIN UI MUST provide summary cards, filterable
  charts, date-range selection, event list/detail, reset, and clear empty/error
  states, with every visualization reflecting the active canonical filter.
