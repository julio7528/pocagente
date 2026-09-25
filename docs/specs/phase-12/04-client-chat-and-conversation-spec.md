# Phase 12.6–12.7 — Conversation Persistence and Client Chat

## Conversation lifecycle

Each conversation has one CLIENT owner and one stable UUID managed by Django.
The portal lifecycle is `ACTIVE`, `WAITING_HUMAN`, `HUMAN`, `CLOSED`,
`BLOCKED`, or `DELETED`. A new conversation starts `ACTIVE`. A pending
`WAITING_CONFIRMATION` agent offer remains `ACTIVE` and is shown as awaiting
client confirmation. A confirmed transfer maps to `WAITING_HUMAN`; operator
acceptance maps to `HUMAN`; assigned human finalization maps to terminal
`CLOSED`. A conversation can enter one human-support lifecycle only; it cannot
return to automation or be escalated again after that lifecycle. ADMIN blocking
and logical deletion are portal controls, not Human Escalation agent states.

The conversation title is created once from the first CLIENT message. The
application trims surrounding whitespace, collapses whitespace runs, retains
normalized text through 50 characters, and otherwise stores the first 47
characters followed by `...`; no LLM is used and later messages do not rename
the conversation.

CLIENT may create, list, reopen, and continue owned `ACTIVE` conversations.
Owned `BLOCKED` and `CLOSED` history is readable but immutable to the client.
`DELETED` is hidden from ordinary client history and is not messageable.
Starting a new conversation never imports history from another conversation.
While `WAITING_HUMAN`, the client may append a follow-up in the same thread for
the support queue, but no AI turn is invoked; the client sees waiting status.
While `HUMAN`, client messages are delivered in the same thread to the assigned
operator and never invoke automation. `BLOCKED` freezes all normal writers;
only ADMIN may unblock and restore the saved prior state. `CLOSED` is terminal
and read-only; new assistance requires a new conversation. `DELETED` is a
soft-deleted tombstone hidden from normal CLIENT history, with no normal restore
workflow; messages and handoff rows remain physically preserved.

## Messages, context, and reliability

Persist the client turn before calling FastAPI, under a stable client-generated
or server-issued UUID idempotency key scoped to the conversation. Persist the
agent result as a separate `AGENT` message in the same conversation. Human
messages use sender `SUPPORT_AGENT` and an authenticated sender-user FK;
system lifecycle notices use `SYSTEM`. Sort by `created_at` plus stable ID.
Normal messages are immutable: CLIENT, SUPPORT_AGENT, and ADMIN cannot edit
historical message bodies. A correction is a new message.

For each agent turn, Django sends only a bounded same-conversation context: at
most the most recent 12 prior messages and 6,000 total characters across
context plus the current turn, ordered oldest-to-newest after truncation. The
current client message is always included and has priority within the ceiling;
oldest prior context is dropped first. The full persisted history remains viewable to authorized
users but is not resent in full to FastAPI. Context is passed as typed message
roles, never as trusted identity or authorization. Conversation IDs are
correlation identifiers, not authentication. FastAPI remains stateless with
respect to portal conversations unless a later reviewed requirement changes
that boundary.

When the current CLIENT message alone exceeds 6,000 characters, Django keeps
the complete immutable message in the portal transcript and emits an explicitly
marked provider-neutral context copy containing its first 6,000 characters.
That context item includes truncation metadata and the original character
count; truncation is never silent and does not modify the persisted message.

If an API call fails before the outcome is known, preserve a pending/controlled
failure state and do not duplicate a transcript row. Automatic retries use the
same turn idempotency key and are bounded. Because the existing FastAPI `/chat`
contract has no durable idempotency store, a timeout after execution may repeat
agent work; Django MUST persist at most one response for a turn key and MUST
not claim exactly-once provider execution. Once agent transport exists in
Phase 12.13, the UI will offer a safe retry/recovery action and keep the user's
original message. Phase 12.7 displays the persisted failure state without an
inactive retry control.

## Client layout and behavior

Authenticated client pages use Header, Sidebar, main conversation area, and
Footer. Sidebar actions include New conversation, owned conversation history,
account, and logout. `ACTIVE` enables input; `WAITING_HUMAN` shows waiting
status and follows handoff rules; `HUMAN` shows updates but suspends AI and
client automation-triggered agent turns; `BLOCKED`/`CLOSED` are read-only;
`DELETED` is absent from normal history. Empty, loading, network-error, and
controlled-agent-failure states are explicit and do not expose internal
diagnostics.

Phase 12.7 provides the authenticated CLIENT browser routes and full portal
transcript. New-conversation and subsequent message forms carry a stable UUID
turn key; a replay of the first form resolves to its existing conversation.
The browser submits only to Django and displays persisted messages without
applying the bounded FastAPI context limit. Until Phase 12.13 activates agent
transport, successful submissions report that the message was registered;
pending and failed turns remain visible without a fabricated AGENT reply or
an inactive retry action.

## Requirements

- **REQ-P12-CLIENT-001:** A CLIENT MUST be able to create and list only its own
  conversations, reopen/continue an owned ACTIVE conversation, and start a
  separate conversation without inherited cross-conversation memory.
- **REQ-P12-CLIENT-002:** Conversation lifecycle MUST use the approved states
  and map existing BOT/confirmation/handoff/human/resolution semantics without
  creating a competing agent state machine.
- **REQ-P12-CLIENT-003:** CLIENT MUST be able to read owned BLOCKED and CLOSED
  history but MUST NOT append messages or invoke agents in those states;
  DELETED conversations MUST be hidden from normal client history.
- **REQ-P12-CLIENT-004:** Every message MUST remain attached to the same
  conversation across AI and human handling, identify sender class and
  authenticated human sender where applicable, and render in stable
  chronological order.
- **REQ-P12-CLIENT-005:** Client turns and agent responses MUST be persisted
  once per conversation-scoped idempotency key; retries MUST NOT duplicate
  transcript rows and MUST NOT claim exactly-once agent execution without a
  backend idempotency guarantee.
- **REQ-P12-CLIENT-006:** FastAPI context MUST be limited to the same
  conversation's most recent 12 prior messages and 6,000 total characters
  including the current turn; current input takes priority and older context
  is dropped first. Role labels are conversation data, not trusted identity.
- **REQ-P12-CLIENT-007:** The client UI MUST provide new conversation,
  conversation history, account/logout controls, message entry, and visible
  state for active, waiting-human, human-owned, blocked, and closed
  conversations.
- **REQ-P12-CLIENT-008:** The client MUST NOT be able to view or mutate another
  user's messages by changing a URL, form field, conversation ID, or request
  body; safe 403/404 behavior is acceptable.
- **REQ-P12-CLIENT-009:** Empty, loading, network, retry, insufficient-evidence,
  and controlled backend failure states MUST be understandable and must not
  expose prompts, secrets, SQL, internal paths, or raw exception details.

The owner-approved HUMAN lifecycle is one-time and terminal on assigned
operator finalization (`HUMAN -> CLOSED`). The portal does not provide a
`HUMAN -> ACTIVE` return-to-automation action.
