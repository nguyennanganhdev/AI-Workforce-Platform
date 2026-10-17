# partner_events — PHH Phase B

Owner: **Phan Huy Hoàng**. Phạm vi PHH-16: public event projection, durable history, authorized snapshot, replay-first SSE và advisory signal sau commit. Module không gửi webhook/outbound HTTP sang đối tác.

Exports chính: `ConversationEventService`, `PublicEventWriter`, `EventRepository`, `ConversationAccess`, `EventCursorExpired`. Repository production và HTTP mapping `410` thuộc Phase C.

Xem [bàn giao Phase B](../../../../../../docs/workforce/handoffs/phan-huy-hoang/PHASE_B.md).
