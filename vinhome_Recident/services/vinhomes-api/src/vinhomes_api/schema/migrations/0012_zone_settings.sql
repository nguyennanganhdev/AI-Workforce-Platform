-- Rules that differ from one zone to another are data, not code.
--
-- Until now these limits were constants in the services: a home may have 10 visits waiting, a visit may be
-- announced 30 days ahead and last 72 hours, family and delivery visits of up to 5 people need no approval, a
-- visitor may enter 15 minutes early, a home holds at most 6 resident cards and 4 vehicle cards, and a paid
-- booking is held 15 minutes for payment. A villa zone and a tower zone do not share them.
--
-- zone_settings holds one row per zone (zone_id set) and may hold one row for the whole tenant (zone_id null).
-- A column left empty inherits: zone, then tenant, then the value written in app_zone_rules below, which are the
-- values the services used until now, so a database with no rows behaves exactly as before.

CREATE TABLE public.zone_settings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    zone_id uuid,
    visit_max_waiting integer,
    visit_max_days_ahead integer,
    visit_max_hours integer,
    visit_auto_approve_purposes text[],
    visit_auto_approve_max_guests integer,
    visit_early_minutes integer,
    card_limit_resident integer,
    card_limit_vehicle integer,
    amenity_payment_hold_minutes integer,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT zone_settings_pkey PRIMARY KEY (id),
    CONSTRAINT zone_settings_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT zone_settings_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT zone_settings_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT zone_settings_visit_max_waiting_check CHECK (visit_max_waiting IS NULL OR visit_max_waiting >= 1),
    CONSTRAINT zone_settings_visit_max_days_ahead_check CHECK (visit_max_days_ahead IS NULL OR visit_max_days_ahead BETWEEN 0 AND 365),
    CONSTRAINT zone_settings_visit_max_hours_check CHECK (visit_max_hours IS NULL OR visit_max_hours BETWEEN 1 AND 720),
    CONSTRAINT zone_settings_visit_purposes_check CHECK (visit_auto_approve_purposes IS NULL
        OR visit_auto_approve_purposes <@ ARRAY['family_visit', 'delivery', 'service_provider', 'business', 'other']::text[]),
    CONSTRAINT zone_settings_visit_auto_guests_check CHECK (visit_auto_approve_max_guests IS NULL OR visit_auto_approve_max_guests >= 0),
    CONSTRAINT zone_settings_visit_early_check CHECK (visit_early_minutes IS NULL OR visit_early_minutes >= 0),
    CONSTRAINT zone_settings_card_limit_resident_check CHECK (card_limit_resident IS NULL OR card_limit_resident >= 0),
    CONSTRAINT zone_settings_card_limit_vehicle_check CHECK (card_limit_vehicle IS NULL OR card_limit_vehicle >= 0),
    CONSTRAINT zone_settings_hold_check CHECK (amenity_payment_hold_minutes IS NULL OR amenity_payment_hold_minutes >= 1)
);
CREATE UNIQUE INDEX zone_settings_zone_uq ON public.zone_settings (tenant_id, zone_id) WHERE zone_id IS NOT NULL;
CREATE UNIQUE INDEX zone_settings_tenant_uq ON public.zone_settings (tenant_id) WHERE zone_id IS NULL;
ALTER TABLE public.zone_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.zone_settings FORCE ROW LEVEL SECURITY;
CREATE POLICY zone_settings_tenant_policy ON public.zone_settings
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER zone_settings_touch BEFORE UPDATE ON public.zone_settings FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

-- The values that apply in a zone (p_zone null: outside any zone). One place says what "no setting" means.
CREATE FUNCTION public.app_zone_rules(p_tenant uuid, p_zone uuid)
 RETURNS TABLE (
    visit_max_waiting integer,
    visit_max_days_ahead integer,
    visit_max_hours integer,
    visit_auto_approve_purposes text[],
    visit_auto_approve_max_guests integer,
    visit_early_minutes integer,
    card_limit_resident integer,
    card_limit_vehicle integer,
    amenity_payment_hold_minutes integer)
 LANGUAGE sql STABLE
AS $function$
 SELECT coalesce(z.visit_max_waiting, t.visit_max_waiting, 10),
        coalesce(z.visit_max_days_ahead, t.visit_max_days_ahead, 30),
        coalesce(z.visit_max_hours, t.visit_max_hours, 72),
        coalesce(z.visit_auto_approve_purposes, t.visit_auto_approve_purposes, ARRAY['family_visit', 'delivery']::text[]),
        coalesce(z.visit_auto_approve_max_guests, t.visit_auto_approve_max_guests, 5),
        coalesce(z.visit_early_minutes, t.visit_early_minutes, 15),
        coalesce(z.card_limit_resident, t.card_limit_resident, 6),
        coalesce(z.card_limit_vehicle, t.card_limit_vehicle, 4),
        coalesce(z.amenity_payment_hold_minutes, t.amenity_payment_hold_minutes, 15)
 FROM (SELECT 1) AS one
 LEFT JOIN public.zone_settings z ON z.tenant_id = p_tenant AND z.zone_id = p_zone
 LEFT JOIN public.zone_settings t ON t.tenant_id = p_tenant AND t.zone_id IS NULL
$function$;
