# Phase 12.8 — Human Escalation and Support-Agent Portal

## Reuse the existing Human Escalation contract

The FastAPI Human Escalation Agent is the authority for valid AI-originated
offers, explicit user confirmation, authorized acceptance, ownership, automation
suspension, and resolution. Its current runtime contract also includes
return-to-automation, but the approved portal lifecycle does not expose that
transition. It currently uses
`BOT`, `WAITING_CONFIRMATION`, `WAITING_HUMAN`, `HUMAN`, and `RESOLVED`, with
`OFFER`, `CONFIRM`, `ACCEPT`, `RETURN_TO_AUTOMATION`, and `RESOLVE` actions.
It is deliberately non-persistent. Django supplies durable storage and
authenticated operator identity; it does not reimplement the agent's reasoning
or bypass its typed transition rules.

Mapping to portal state:

| Runtime state/transition | Portal representation |
|---|---|
| BOT | conversation `ACTIVE`; no handoff |
| WAITING_CONFIRMATION | conversation remains `ACTIVE`; show pending client confirmation |
| confirmed WAITING_HUMAN | conversation `WAITING_HUMAN`; handoff `WAITING` |
| authorized ACCEPT -> HUMAN | conversation `HUMAN`; handoff `ASSIGNED`; assigned operator; automation suspended |
| assigned RESOLVE -> RESOLVED | after support-agent finalization, conversation `CLOSED`; handoff `RESOLVED` |

Each conversation may have at most one SupportHandoff for its entire lifetime.
The portal will not invoke `RETURN_TO_AUTOMATION`; after confirmation and
assignment the allowed completion is finalization to `CLOSED`. A new customer
need requires a new conversation. This owner decision narrows the portal flow
without changing or duplicating the existing FastAPI agent state machine.

Phase 12.8 implements only the narrow authenticated internal transition
transport needed for explicit client confirmation, operator acceptance, and
assigned-operator resolution. Django calls this typed boundary before it
commits the corresponding portal state. It does not implement agent execution,
AI-originated `/chat` turns, or the general Django/FastAPI client; those remain
Phase 12.13. A client-initiated request must pass through a separate explicit
confirmation action before it becomes queue-visible.

## Queue, ownership, and message flow

The support portal has Waiting for support, My active conversations, and
Finalized conversations views. A `SUPPORT_AGENT` sees waiting handoffs and only
the human conversations assigned to that user; final history visibility is
limited to authorized support policy. Accept/claim uses one database
transaction and a conditional status transition or row lock. Exactly one
concurrent claimant succeeds; other claimants receive a safe conflict and
refresh the queue. Claim records actor, accepted time, and assignment before
human messages are accepted.

AI escalation occurs only after the existing agent's explicit confirmation.
The minimal sanitized runtime handoff package remains distinct from full chat
history; the assigned human may read the same conversation thread under access
policy. While `HUMAN`, no new automated agent response is generated. Human
messages persist as `SUPPORT_AGENT` messages in the same conversation.
Finalization by the assigned operator sends the existing `RESOLVE` transition
and atomically closes the portal conversation. The client can still read the
thread; client, support agent, and agent cannot append after close. The assigned
operator may finalize the handoff; no return-to-automation action is exposed.

## Polling

Use authenticated HTTP polling with an initial interval near 12 seconds for
support queue counts/list updates and client/support message updates while
waiting or human-owned. Poll immediately after a user action, pause when the page is not
visible, use bounded backoff on errors, and deduplicate by stable message ID.
Keep newest update cursors and deterministic message order. Interval tuning
can be measured later; WebSockets/Channels are not part of the initial POC.

## Requirements

- **REQ-P12-SUPPORT-001:** The portal MUST reuse the existing FastAPI Human
  Escalation transition contract and MUST NOT introduce a second agent-owned
  escalation state machine.
- **REQ-P12-SUPPORT-002:** A human handoff MUST become queue-visible only
  after explicit client confirmation and the runtime's `WAITING_HUMAN`
  transition; an offer alone MUST NOT imply transfer or operator acceptance.
- **REQ-P12-SUPPORT-003:** Handoff persistence MUST map runtime waiting,
  human-owned, and resolution transitions to the approved portal statuses and
  conversation lifecycle; the portal MUST NOT expose return-to-automation.
- **REQ-P12-SUPPORT-004:** A SUPPORT_AGENT MUST see waiting work, assigned
  active work, and permitted finalized work only within the server-enforced
  role/assignment policy.
- **REQ-P12-SUPPORT-005:** Handoff acceptance MUST be atomic so only one
  SUPPORT_AGENT can claim a WAITING item; a losing concurrent claimant MUST
  receive a controlled conflict without creating a second owner.
- **REQ-P12-SUPPORT-006:** Acceptance, human messages, and resolution MUST use
  the authenticated assigned operator; another support user cannot silently
  take over or finalize ownership.
- **REQ-P12-SUPPORT-007:** While a conversation is HUMAN-owned, AI execution
  MUST be suspended; human messages MUST append to the same conversation and
  preserve the shared ordered history.
- **REQ-P12-SUPPORT-008:** Finalization MUST use the runtime's explicit
  resolution transition, close the portal conversation, preserve readable
  client history, and prohibit further client/AI messages in that conversation.
- **REQ-P12-SUPPORT-009:** Support queue/message updates MUST use authenticated
  polling initially (about 12 seconds, configurable), stable cursors, duplicate
  prevention, bounded error backoff, and no WebSocket dependency.

The owner-approved lifecycle is one human-support cycle per conversation:
`ACTIVE -> WAITING_HUMAN -> HUMAN -> CLOSED`. `CLOSED` is terminal for normal
interaction; the conversation cannot be reopened or escalated again.
