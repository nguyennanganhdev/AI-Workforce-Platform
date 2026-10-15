-- A request that is resolved but not closed waits for the resident; one that is closed is complete.
--
-- 0009 completed a case as soon as its request was resolved. In the resident app a resolved request is
-- "waiting for your answer": the resident confirms it or asks for it to be done again. Now a resolved request gets a
-- case in 'confirmation' with the published result, and a closed one gets the resident's confirmation, a
-- 'completed' case and, as the closing line of the timeline, the one the app writes when the resident confirms.
--
-- Only app_ensure_case changes. Cases that 0009 already made for a request that was resolved and not yet closed keep
-- the status they have; the sample data holds none (its requests are all open).

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
  -- The finished work is published to the resident; a resolved request waits for the resident's answer,
  -- a closed one has had it (the resident confirmed) and the case is complete.
  res := md5('resident-resolution:' || t.id::text)::uuid;
  INSERT INTO vh_resident_resolutions (id, tenant_id, case_id, summary, published_by, basis_versions, published_at)
  VALUES (res, t.tenant_id, c, 'Phản ánh đã được xử lý.', t.requester_user_id, jsonb_build_object(t.id::text, t.version),
          coalesce(t.resolved_at, t.updated_at));
  IF t.status = 'closed' THEN
   INSERT INTO vh_resident_resolution_responses (tenant_id, case_id, resolution_id, actor_id, decision, created_at)
   VALUES (t.tenant_id, c, res, t.requester_user_id, 'confirm', coalesce(t.closed_at, t.resolved_at, t.updated_at));
   UPDATE vh_resident_cases SET status = 'completed', current_resolution_id = res,
          updated_at = coalesce(t.closed_at, t.resolved_at, t.updated_at)
   WHERE id = c AND tenant_id = t.tenant_id;
   -- The line the app writes when the resident confirms, dated just after the request was closed.
   PERFORM app_case_event(t.tenant_id, c, 'Bạn đã xác nhận kết quả', 'resident.case.confirm',
                          coalesce(t.closed_at, t.resolved_at, t.updated_at) + interval '1 second');
  ELSE
   UPDATE vh_resident_cases SET status = 'confirmation', current_resolution_id = res,
          updated_at = coalesce(t.resolved_at, t.updated_at)
   WHERE id = c AND tenant_id = t.tenant_id;
  END IF;
 END IF;
 RETURN c;
END
$function$;
