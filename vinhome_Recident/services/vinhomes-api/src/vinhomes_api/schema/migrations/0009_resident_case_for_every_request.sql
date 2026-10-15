-- Every request a resident starts has a resident case (vh_resident_cases), whichever door it came through.
--
-- The resident app lists, follows and confirms its requests through the case. Until now only the app's own form
-- created one, so a request reported to Reception in the chat existed as a ticket the resident could not see in
-- the list. app_ensure_case(ticket) gives a ticket its case: the case is linked to the ticket, carries the public
-- timeline, and a ticket that is already finished gets a closed case. It does nothing when the ticket already has a
-- case, has no unit, or was cancelled, so it can be called as often as needed. One chat has one case: a further
-- request from the same chat is added to that case (the case is reopened if it had been completed).
--
-- The case id is derived from the ticket id, so the same ticket always gets the same case (the mock world relies on it).

CREATE OR REPLACE FUNCTION public.app_ensure_case(p_ticket uuid)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE
 t tickets;
 place record;
 c uuid;
 res uuid;
 description_text text;
 title_text text;
 started timestamptz;
BEGIN
 SELECT * INTO t FROM tickets WHERE id = p_ticket;
 IF NOT FOUND OR t.unit_id IS NULL OR t.building_id IS NULL OR t.site_id IS NULL OR t.status = 'cancelled' THEN
  RETURN NULL;
 END IF;
 SELECT case_id INTO c FROM vh_resident_case_tickets WHERE tenant_id = t.tenant_id AND ticket_id = t.id LIMIT 1;
 IF FOUND THEN
  RETURN c;
 END IF;
 -- One chat has at most one case (a case can follow several requests): a further request of the same chat joins it.
 SELECT id INTO c FROM vh_resident_cases WHERE tenant_id = t.tenant_id AND channel_id = t.channel_id;
 IF FOUND THEN
  INSERT INTO vh_resident_case_tickets (tenant_id, case_id, ticket_id, linked_by, created_at)
  VALUES (t.tenant_id, c, t.id, t.requester_user_id, t.created_at);
  IF t.status NOT IN ('resolved', 'closed')
     AND (SELECT status FROM vh_resident_cases WHERE id = c AND tenant_id = t.tenant_id) <> 'processing' THEN
   UPDATE vh_resident_cases SET status = 'processing', current_resolution_id = NULL, version = version + 1, updated_at = now()
   WHERE id = c AND tenant_id = t.tenant_id;
   PERFORM app_case_event(t.tenant_id, c, 'Đã chuyển phản ánh đến bộ phận xử lý', 'resident.case.routed', now());
  END IF;
  RETURN c;
 END IF;
 SELECT u.code AS unit_code, b.name AS building_name INTO place
 FROM units u JOIN buildings b ON b.id = t.building_id AND b.tenant_id = t.tenant_id
 WHERE u.id = t.unit_id AND u.tenant_id = t.tenant_id;
 IF NOT FOUND THEN
  RETURN NULL;
 END IF;

 c := md5('resident-case:' || t.id::text)::uuid;
 started := t.created_at;
 description_text := left(t.description, 5000);
 IF length(description_text) < 8 THEN
  description_text := left(description_text || ' (báo qua trò chuyện)', 5000);
 END IF;
 title_text := left(regexp_replace(btrim(t.title), '\s+', ' ', 'g'), 90);
 IF title_text = '' THEN
  title_text := 'Phản ánh của cư dân';
 END IF;

 INSERT INTO vh_resident_cases
   (id, tenant_id, requester_user_id, unit_id, building_id, site_id, domain_id, channel_id, code, title, description,
    location_description, location_label, status, created_at, updated_at)
 VALUES
   (c, t.tenant_id, t.requester_user_id, t.unit_id, t.building_id, t.site_id, t.domain_id, t.channel_id,
    'YC-' || upper(left(replace(c::text, '-', ''), 12)), title_text, description_text,
    'Căn ' || place.unit_code, place.building_name || ' · ' || place.unit_code, 'processing', started, started);
 INSERT INTO vh_resident_submissions (tenant_id, case_id, submitted_by, description, location_description, created_at)
 VALUES (t.tenant_id, c, t.requester_user_id, description_text, 'Căn ' || place.unit_code, started);
 INSERT INTO vh_resident_case_tickets (tenant_id, case_id, ticket_id, linked_by, created_at)
 VALUES (t.tenant_id, c, t.id, t.requester_user_id, started);   -- linked_by and published_by name users, so the requester stands in for the system

 -- The two entries a case gets when it is received and routed, in the same words the app's own flow writes.
 PERFORM app_case_event(t.tenant_id, c, 'Đã tiếp nhận phản ánh', 'resident.case.created', started);
 PERFORM app_case_event(t.tenant_id, c, 'Đã chuyển phản ánh đến bộ phận xử lý', 'resident.case.routed', started + interval '1 second');

 IF t.status IN ('resolved', 'closed') THEN
  res := md5('resident-resolution:' || t.id::text)::uuid;
  INSERT INTO vh_resident_resolutions (id, tenant_id, case_id, summary, published_by, basis_versions, published_at)
  VALUES (res, t.tenant_id, c, 'Phản ánh đã được xử lý.', t.requester_user_id, jsonb_build_object(t.id::text, t.version),
          coalesce(t.resolved_at, t.updated_at));
  UPDATE vh_resident_cases SET status = 'completed', current_resolution_id = res, updated_at = coalesce(t.resolved_at, t.updated_at)
  WHERE id = c AND tenant_id = t.tenant_id;
  PERFORM app_case_event(t.tenant_id, c, 'Phản ánh đã hoàn tất', 'resident.case.completed', coalesce(t.resolved_at, t.updated_at));
 END IF;
 RETURN c;
END
$function$;

-- One public timeline entry and its outbox row (what resident_cases.event() writes from the app).
CREATE OR REPLACE FUNCTION public.app_case_event(p_tenant uuid, p_case uuid, p_label text, p_type text, p_at timestamptz)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE e uuid;
BEGIN
 INSERT INTO vh_resident_public_events (tenant_id, case_id, label, occurred_at)
 VALUES (p_tenant, p_case, p_label, p_at) RETURNING id INTO e;
 INSERT INTO vh_resident_outbox (tenant_id, case_id, event_id, event_type, payload)
 VALUES (p_tenant, p_case, e, p_type, jsonb_build_object('caseId', p_case));
END
$function$;

-- Requests that already exist get their case. (Run by the database owner; a role that row-level security
-- hides the tickets from has nothing to do here.)
SELECT app_ensure_case(id) FROM tickets ORDER BY created_at, id;
