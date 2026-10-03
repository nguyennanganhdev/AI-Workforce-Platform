"""Composition of the Supervisor for the Vinhomes business API.

Team Đông's Supervisor and group chat cores are used as they are. This package supplies what
they need from outside for the Reception V2 exchange, bound to the business API's
`/internal/coordination/v1` endpoints (services/vinhomes-api, v3_coordination.py):

  backend.py   HTTP client: one method per endpoint, definite refusal vs unknown outcome
  ports.py     ReceptionPort and Authority over that client; the ports with no producer yet
  runtime.py   inbox poller, worker and the ASGI service (`python -m vinhomes`)

Bound so far: a ticket handed over by Reception is verified, a durable session is created and
`accepted` is sent back. Rooms, specialists, plans and backend actions have no producer
contract yet; their ports refuse, and the session pauses with the reason.
"""
