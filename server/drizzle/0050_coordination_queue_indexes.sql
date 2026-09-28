CREATE INDEX "vh_provider_event_received_ix" ON "vh_provider_event" USING btree ("tenant_id","status","received_at");--> statement-breakpoint
CREATE INDEX "vh_notification_delivery_ready_ix" ON "vh_notification_delivery" USING btree ("tenant_id","status","available_at");--> statement-breakpoint
CREATE INDEX "vh_incident_sla_response_ix" ON "vh_incident_sla" USING btree ("tenant_id","response_due_at") WHERE "vh_incident_sla"."responded_at" is null;--> statement-breakpoint
CREATE INDEX "vh_incident_sla_resolution_ix" ON "vh_incident_sla" USING btree ("tenant_id","resolution_due_at") WHERE "vh_incident_sla"."resolved_at" is null;--> statement-breakpoint
CREATE INDEX "platform_handoff_ready_ix" ON "platform_handoff" USING btree ("tenant_id","status","next_attempt_at");--> statement-breakpoint
CREATE INDEX "platform_session_control_lease_ix" ON "platform_session_control" USING btree ("tenant_id","lease_expires_at");--> statement-breakpoint
CREATE INDEX "platform_session_wait_deadline_ix" ON "platform_session_wait" USING btree ("tenant_id","status","deadline_at");--> statement-breakpoint
CREATE INDEX "platform_event_receipt_ready_ix" ON "platform_event_receipt" USING btree ("tenant_id","status","available_at");