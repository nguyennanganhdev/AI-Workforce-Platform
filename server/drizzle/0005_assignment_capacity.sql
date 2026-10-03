-- Completed work retains its executor for evidence and customer acceptance.
-- Only assignments on unfinished work consume concurrent job capacity.
CREATE OR REPLACE FUNCTION app_assignment_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE capacity integer; used integer;
BEGIN
 IF NEW.status NOT IN ('offered','accepted') THEN RETURN NEW; END IF;
 SELECT max_concurrent_jobs INTO STRICT capacity FROM staff_profiles
 WHERE id=NEW.staff_id AND tenant_id=NEW.tenant_id FOR UPDATE;
 SELECT count(*) INTO used FROM work_assignments a
 JOIN work_orders w ON w.id=a.work_order_id AND w.tenant_id=a.tenant_id
 WHERE a.tenant_id=NEW.tenant_id AND a.staff_id=NEW.staff_id AND a.id<>NEW.id
 AND w.status NOT IN ('completed','cancelled','rejected')
 AND (a.status='accepted' OR (a.status='offered' AND a.offer_expires_at>now()));
 IF used>=capacity THEN RAISE EXCEPTION 'Staff capacity exhausted' USING ERRCODE='23514'; END IF;
 IF NEW.status='offered' AND (NEW.offer_expires_at IS NULL OR NEW.offer_expires_at<=now()) THEN RAISE EXCEPTION 'Offer must have a future expiry'; END IF;
 IF NEW.status='accepted' AND (NEW.accepted_at IS NULL OR NEW.eta_at IS NULL) THEN RAISE EXCEPTION 'Accepted assignment requires acknowledgment and ETA'; END IF;
 RETURN NEW;
END $$;
