"""Composition of the Supervisor for the Vinhomes business API.

Team Đông's Supervisor and group chat cores are used as they are. This package supplies what
they need from outside for the Reception V2 exchange, bound to the business API's
`/internal/coordination/v1` endpoints (services/vinhomes-api, v3_coordination.py):

  backend.py   HTTP client: one method per endpoint, definite refusal vs unknown outcome
  ports.py     the Supervisor's ports over that client (Reception, authority, room members,
               releases, specialists on OpenBot, the planner model); the ports with no producer yet
  runtime.py   inbox poller, worker and the ASGI service (`python -m vinhomes`)
  publish.py   an agent definition through draft, evaluation and admin review (`python -m vinhomes.publish`)

Bound so far: a ticket handed over by Reception is verified, a durable session is created and
`accepted` is sent back; with a planner model and an OpenBot configured, a room is opened with
the published specialists of the ticket's category, they are given tasks and their replies are
mirrored to the backend. Plans, resident questions, approvals, backend actions and tools have
no producer contract yet; their ports refuse, and the session pauses with the reason.
"""
