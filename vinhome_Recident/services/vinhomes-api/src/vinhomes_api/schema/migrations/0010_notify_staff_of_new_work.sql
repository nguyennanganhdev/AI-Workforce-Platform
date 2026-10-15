-- A staff member is told, with a record that lasts, when work is offered to them.
--
-- Work reaches a person by three routes (a manager assigns it, an approved plan names the performer, a freed
-- slot takes the next queued job); all of them insert a work_assignments row in status 'offered'. One trigger
-- on that insert covers every route, present and future, and writes the in-app notification the person reads
-- through GET /my/notifications. A row has the assignment in its key, so a retry cannot tell them twice, and a
-- re-offer after a refusal (a new assignment) tells them again.
--
-- This is the in-app record only. Nothing here sends a push, SMS or e-mail: that needs a provider and a worker
-- that reads notification_deliveries rows left in status 'pending' for those channels.

CREATE OR REPLACE FUNCTION public.app_notify_work_offered()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
 s record;
BEGIN
 SELECT sp.user_id, w.id AS work_order_id, w.ticket_id, t.code, t.title INTO s
 FROM staff_profiles sp
 JOIN work_orders w ON w.id = NEW.work_order_id AND w.tenant_id = NEW.tenant_id
 JOIN tickets t ON t.id = w.ticket_id AND t.tenant_id = w.tenant_id
 WHERE sp.id = NEW.staff_id AND sp.tenant_id = NEW.tenant_id;
 IF NOT FOUND OR s.user_id IS NULL THEN
  RETURN NEW;
 END IF;
 INSERT INTO notification_deliveries (tenant_id, user_id, channel, dedupe_key, payload, status, available_at)
 VALUES (NEW.tenant_id, s.user_id, 'in_app', 'work_assignment:' || NEW.id || ':offered',
         jsonb_build_object('type', 'work.offered', 'assignmentId', NEW.id, 'workOrderId', s.work_order_id,
                            'ticketId', s.ticket_id, 'ticketCode', s.code, 'title', s.title,
                            'offerExpiresAt', NEW.offer_expires_at, 'appointmentAt', NEW.eta_at),
         'pending', now())
 ON CONFLICT (tenant_id, user_id, channel, dedupe_key) DO NOTHING;
 RETURN NEW;
END
$function$;

CREATE TRIGGER work_assignments_notify_offer
 AFTER INSERT ON public.work_assignments
 FOR EACH ROW WHEN (NEW.status = 'offered')
 EXECUTE FUNCTION public.app_notify_work_offered();
