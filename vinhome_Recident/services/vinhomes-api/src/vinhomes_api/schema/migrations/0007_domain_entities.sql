-- Entities the golden scenarios need beyond the incident-to-work-order flow (docs/domain/KICH_BAN_VANG.md).
-- Names follow the package (plural, uuid, tenant_id with forced row level security). Content comes from the
-- reference model in docs/domain/KE_HOACH_TRIEN_KHAI.md section 2, trimmed to what a scenario uses.

-- ===== which status may follow which =====
-- One reference table instead of a trigger per table. The trigger below reads it, so a status the
-- table does not list can never be written, whoever writes it. `actors` says who may make the move;
-- the API checks that, the database checks that the move exists.

CREATE TABLE public.state_transitions (
    entity text NOT NULL,
    from_status text NOT NULL,
    to_status text NOT NULL,
    actors text[] NOT NULL,
    rule text DEFAULT '' NOT NULL,
    CONSTRAINT state_transitions_pkey PRIMARY KEY (entity, from_status, to_status)
);
COMMENT ON TABLE public.state_transitions IS 'from_status empty means the status a new row may start in';

CREATE FUNCTION public.app_enforce_transition() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NOT EXISTS (SELECT 1 FROM state_transitions WHERE entity = TG_TABLE_NAME AND from_status = '' AND to_status = NEW.status) THEN
      RAISE EXCEPTION 'A new % cannot start as %', TG_TABLE_NAME, NEW.status USING ERRCODE = 'check_violation';
    END IF;
  ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
    IF NOT EXISTS (SELECT 1 FROM state_transitions WHERE entity = TG_TABLE_NAME AND from_status = OLD.status AND to_status = NEW.status) THEN
      RAISE EXCEPTION '% cannot go from % to %', TG_TABLE_NAME, OLD.status, NEW.status USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END
$$;


INSERT INTO public.state_transitions (entity, from_status, to_status, actors, rule) VALUES
  ('service_requests', '', 'draft', ARRAY['system']::text[], 'initial status'),
  ('service_requests', 'draft', 'submitted', ARRAY['resident']::text[], 'Gửi đơn; tính sla_due_at từ default_sla_hours'),
  ('service_requests', 'submitted', 'in_review', ARRAY['staff','agent']::text[], 'Tiếp nhận, kiểm tra đủ hồ sơ'),
  ('service_requests', 'submitted', 'approved', ARRAY['system']::text[], 'Loại dịch vụ có requires_approval = false'),
  ('service_requests', 'in_review', 'need_more_info', ARRAY['staff','agent']::text[], 'Thiếu giấy tờ; gửi thông báo nêu rõ thứ còn thiếu'),
  ('service_requests', 'need_more_info', 'in_review', ARRAY['resident']::text[], 'Bổ sung hồ sơ'),
  ('service_requests', 'need_more_info', 'cancelled', ARRAY['system','resident']::text[], 'Quá 7 ngày không bổ sung; Huỷ trước khi hoàn tất'),
  ('service_requests', 'in_review', 'approved', ARRAY['staff']::text[], 'Duyệt; agent chỉ được đề xuất'),
  ('service_requests', 'in_review', 'rejected', ARRAY['staff']::text[], 'Từ chối, bắt buộc có decision_note'),
  ('service_requests', 'approved', 'fulfilled', ARRAY['staff']::text[], 'Đã cấp thẻ, đã cập nhật nhân khẩu, đã thực hiện xong; sinh dòng phí nếu fee_amount > 0'),
  ('service_requests', 'submitted', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi hoàn tất'),
  ('service_requests', 'in_review', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi hoàn tất'),
  ('service_requests', 'approved', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi hoàn tất'),
  ('visitor_passes', '', 'pending_approval', ARRAY['system']::text[], 'initial status'),
  ('visitor_passes', 'pending_approval', 'approved', ARRAY['staff','system']::text[], 'Tự duyệt nếu phân khu không yêu cầu duyệt; sinh qr_token'),
  ('visitor_passes', 'pending_approval', 'rejected', ARRAY['staff']::text[], 'Căn đang bị hạn chế hoặc thông tin không hợp lệ'),
  ('visitor_passes', 'approved', 'checked_in', ARRAY['guard','system']::text[], 'Quét QR tại cổng trong khoảng visit_from đến visit_to'),
  ('visitor_passes', 'checked_in', 'checked_out', ARRAY['guard','system']::text[], 'Khách ra'),
  ('visitor_passes', 'approved', 'expired', ARRAY['system']::text[], 'Quá visit_to mà chưa vào'),
  ('visitor_passes', 'pending_approval', 'cancelled', ARRAY['resident']::text[], 'Cư dân huỷ'),
  ('visitor_passes', 'approved', 'cancelled', ARRAY['resident']::text[], 'Cư dân huỷ'),
  ('access_cards', '', 'pending_issue', ARRAY['system']::text[], 'initial status'),
  ('access_cards', 'pending_issue', 'active', ARRAY['staff']::text[], 'In và giao thẻ theo đơn đã duyệt'),
  ('access_cards', 'active', 'suspended', ARRAY['staff','system']::text[], 'Nợ phí gửi xe quá hạn theo chính sách hoặc vi phạm'),
  ('access_cards', 'suspended', 'active', ARRAY['staff','system']::text[], 'Đã thanh toán hoặc hết thời hạn xử lý'),
  ('access_cards', 'active', 'lost', ARRAY['resident','staff']::text[], 'Báo mất; khoá ngay'),
  ('access_cards', 'lost', 'revoked', ARRAY['staff']::text[], 'Khi cấp lại thẻ mới'),
  ('access_cards', 'active', 'expired', ARRAY['system']::text[], 'Quá valid_to'),
  ('access_cards', 'active', 'revoked', ARRAY['staff']::text[], 'Huỷ thẻ, chuyển đi, bán xe'),
  ('access_cards', 'suspended', 'revoked', ARRAY['staff']::text[], 'Huỷ thẻ, chuyển đi, bán xe'),
  ('access_cards', 'expired', 'revoked', ARRAY['staff']::text[], 'Huỷ thẻ, chuyển đi, bán xe'),
  ('debit_notes', '', 'draft', ARRAY['system']::text[], 'initial status'),
  ('debit_notes', 'draft', 'issued', ARRAY['finance','system']::text[], 'Phát hành kỳ; gửi thông báo cho căn'),
  ('debit_notes', 'issued', 'partially_paid', ARRAY['system']::text[], 'Có phân bổ thanh toán nhưng chưa đủ'),
  ('debit_notes', 'issued', 'paid', ARRAY['system']::text[], 'paid_amount = total_amount'),
  ('debit_notes', 'partially_paid', 'paid', ARRAY['system']::text[], 'paid_amount = total_amount'),
  ('debit_notes', 'issued', 'overdue', ARRAY['system']::text[], 'Quá due_date mà chưa trả đủ'),
  ('debit_notes', 'partially_paid', 'overdue', ARRAY['system']::text[], 'Quá due_date mà chưa trả đủ'),
  ('debit_notes', 'overdue', 'paid', ARRAY['system']::text[], 'Trả đủ sau hạn'),
  ('debit_notes', 'draft', 'cancelled', ARRAY['finance']::text[], 'Phát hành sai; phải có ghi chú và phát hành lại chứng từ khác'),
  ('debit_notes', 'issued', 'cancelled', ARRAY['finance']::text[], 'Phát hành sai; phải có ghi chú và phát hành lại chứng từ khác'),
  ('amenity_bookings', '', 'pending_payment', ARRAY['system']::text[], 'initial status'),
  ('amenity_bookings', 'pending_payment', 'confirmed', ARRAY['system']::text[], 'Thanh toán thành công; lượt miễn phí tạo thẳng ở confirmed'),
  ('amenity_bookings', 'pending_payment', 'expired', ARRAY['system']::text[], 'Quá 15 phút chưa thanh toán'),
  ('amenity_bookings', 'confirmed', 'checked_in', ARRAY['staff','system']::text[], 'Quét QR tại tiện ích'),
  ('amenity_bookings', 'checked_in', 'completed', ARRAY['system']::text[], 'Hết khung giờ'),
  ('amenity_bookings', 'confirmed', 'no_show', ARRAY['system']::text[], 'Quá giờ bắt đầu 15 phút không tới'),
  ('amenity_bookings', 'pending_payment', 'cancelled', ARRAY['resident','staff','system','agent']::text[], 'Cư dân huỷ trước cancel_before_hours; hệ thống huỷ khi có lịch đóng; hoàn tiền nếu đã trả'),
  ('amenity_bookings', 'confirmed', 'cancelled', ARRAY['resident','staff','system','agent']::text[], 'Cư dân huỷ trước cancel_before_hours; hệ thống huỷ khi có lịch đóng; hoàn tiền nếu đã trả'),
  ('construction_permits', '', 'draft', ARRAY['system']::text[], 'initial status'),
  ('construction_permits', 'draft', 'submitted', ARRAY['resident']::text[], 'Gửi hồ sơ kèm bản vẽ, cam kết'),
  ('construction_permits', 'submitted', 'appraised', ARRAY['staff']::text[], 'Kỹ thuật thẩm định hồ sơ'),
  ('construction_permits', 'submitted', 'rejected', ARRAY['staff','manager']::text[], 'Từ chối kèm reject_reason'),
  ('construction_permits', 'appraised', 'rejected', ARRAY['staff','manager']::text[], 'Từ chối kèm reject_reason'),
  ('construction_permits', 'appraised', 'approved', ARRAY['manager']::text[], 'Trưởng ban duyệt'),
  ('construction_permits', 'approved', 'awaiting_deposit', ARRAY['system']::text[], 'Quy định yêu cầu đặt cọc'),
  ('construction_permits', 'approved', 'in_progress', ARRAY['system']::text[], 'Không yêu cầu cọc và đã tới planned_start'),
  ('construction_permits', 'awaiting_deposit', 'in_progress', ARRAY['system']::text[], 'Cọc ở trạng thái held, thợ đã được duyệt, tới planned_start'),
  ('construction_permits', 'in_progress', 'suspended', ARRAY['staff','system']::text[], 'Đơn phát sinh tạm dừng được duyệt, hoặc đình chỉ do vi phạm'),
  ('construction_permits', 'suspended', 'in_progress', ARRAY['staff','system']::text[], 'Đơn phát sinh tiếp tục được duyệt'),
  ('construction_permits', 'in_progress', 'expired', ARRAY['system']::text[], 'Quá planned_end mà không có gia hạn'),
  ('construction_permits', 'expired', 'in_progress', ARRAY['system']::text[], 'Đơn phát sinh gia hạn được duyệt'),
  ('construction_permits', 'in_progress', 'awaiting_acceptance', ARRAY['system']::text[], 'Đơn phát sinh xin nghiệm thu được duyệt'),
  ('construction_permits', 'awaiting_acceptance', 'completed', ARRAY['staff']::text[], 'Kiểm tra nghiệm thu đạt; mở thủ tục hoàn cọc'),
  ('construction_permits', 'awaiting_acceptance', 'in_progress', ARRAY['staff']::text[], 'Nghiệm thu không đạt, phải làm lại'),
  ('construction_permits', 'draft', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi thi công'),
  ('construction_permits', 'submitted', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi thi công'),
  ('construction_permits', 'appraised', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi thi công'),
  ('construction_permits', 'approved', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi thi công'),
  ('construction_permits', 'awaiting_deposit', 'cancelled', ARRAY['resident']::text[], 'Huỷ trước khi thi công'),
  ('announcements', '', 'draft', ARRAY['system']::text[], 'initial status'),
  ('announcements', 'draft', 'scheduled', ARRAY['staff']::text[], 'Hẹn giờ phát'),
  ('announcements', 'draft', 'published', ARRAY['staff','system']::text[], 'Phát hành; sinh notification cho tài khoản trong phạm vi'),
  ('announcements', 'scheduled', 'published', ARRAY['staff','system']::text[], 'Phát hành; sinh notification cho tài khoản trong phạm vi'),
  ('announcements', 'published', 'archived', ARRAY['staff','system']::text[], 'Quá expire_at hoặc gỡ'),
  ('amenity_bookings', '', 'confirmed', ARRAY['system']::text[], 'initial status for a booking that costs nothing');


-- ===== money owed =====

CREATE TABLE public.debit_notes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    doc_no text NOT NULL,
    unit_id uuid NOT NULL,
    period_month date,
    kind text DEFAULT 'monthly' NOT NULL,
    issue_date date NOT NULL,
    due_date date NOT NULL,
    subtotal bigint NOT NULL,
    vat_amount bigint DEFAULT 0 NOT NULL,
    total_amount bigint NOT NULL,
    paid_amount bigint DEFAULT 0 NOT NULL,
    status text NOT NULL,
    payer_user_id text,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT debit_notes_pkey PRIMARY KEY (id),
    CONSTRAINT debit_notes_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT debit_notes_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT debit_notes_doc_no_uq UNIQUE (tenant_id, doc_no),
    CONSTRAINT debit_notes_kind_check CHECK (kind IN ('monthly', 'adhoc', 'deposit', 'penalty')),
    CONSTRAINT debit_notes_status_check CHECK (status IN ('draft', 'issued', 'partially_paid', 'paid', 'overdue', 'cancelled')),
    CONSTRAINT debit_notes_amounts_check CHECK (subtotal >= 0 AND vat_amount >= 0 AND total_amount = subtotal + vat_amount AND paid_amount >= 0 AND paid_amount <= total_amount),
    CONSTRAINT debit_notes_paid_check CHECK (status <> 'paid' OR paid_amount = total_amount),
    CONSTRAINT debit_notes_due_check CHECK (due_date >= issue_date),
    CONSTRAINT debit_notes_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT debit_notes_payer_user_id_fk FOREIGN KEY (payer_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX debit_notes_unit_idx ON public.debit_notes (tenant_id, unit_id, issue_date DESC);
CREATE INDEX debit_notes_open_idx ON public.debit_notes (tenant_id, due_date) WHERE status IN ('issued', 'partially_paid', 'overdue');
ALTER TABLE public.debit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.debit_notes FORCE ROW LEVEL SECURITY;
CREATE POLICY debit_notes_tenant_policy ON public.debit_notes
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER debit_notes_touch BEFORE UPDATE ON public.debit_notes FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER debit_notes_transition BEFORE INSERT OR UPDATE OF status ON public.debit_notes FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

CREATE TABLE public.debit_note_lines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    debit_note_id uuid NOT NULL,
    line_no integer NOT NULL,
    fee_kind text NOT NULL,
    description text NOT NULL,
    quantity numeric(14,3) DEFAULT 1 NOT NULL,
    unit_price bigint NOT NULL,
    vat_rate numeric(6,3) DEFAULT 0 NOT NULL,
    amount bigint NOT NULL,
    service_from date,
    service_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT debit_note_lines_pkey PRIMARY KEY (id),
    CONSTRAINT debit_note_lines_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT debit_note_lines_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT debit_note_lines_no_uq UNIQUE (debit_note_id, line_no),
    CONSTRAINT debit_note_lines_fee_kind_check CHECK (fee_kind IN ('management', 'parking', 'water', 'electricity', 'service', 'deposit', 'penalty', 'other')),
    CONSTRAINT debit_note_lines_amount_check CHECK (amount >= 0 AND quantity > 0),
    CONSTRAINT debit_note_lines_debit_note_id_fk FOREIGN KEY (tenant_id, debit_note_id) REFERENCES public.debit_notes(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX debit_note_lines_note_idx ON public.debit_note_lines (tenant_id, debit_note_id);
ALTER TABLE public.debit_note_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.debit_note_lines FORCE ROW LEVEL SECURITY;
CREATE POLICY debit_note_lines_tenant_policy ON public.debit_note_lines
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER debit_note_lines_touch BEFORE UPDATE ON public.debit_note_lines FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE FUNCTION public.app_check_debit_note_lines() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- A note that leaves draft must be exactly what its lines add up to.
  IF OLD.status = 'draft' AND NEW.status NOT IN ('draft', 'cancelled') THEN
    IF COALESCE((SELECT sum(amount) FROM debit_note_lines WHERE debit_note_id = NEW.id), 0) <> NEW.subtotal THEN
      RAISE EXCEPTION 'Debit note % lines do not add up to its subtotal', NEW.doc_no USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER debit_notes_lines_total BEFORE UPDATE OF status ON public.debit_notes FOR EACH ROW EXECUTE FUNCTION public.app_check_debit_note_lines();

-- ===== vehicles, cards and who came through a gate =====

CREATE TABLE public.vehicles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    unit_id uuid NOT NULL,
    owner_user_id text,
    owner_name text NOT NULL,
    kind text NOT NULL,
    plate_no text,
    brand text,
    model text,
    color text,
    status text DEFAULT 'active' NOT NULL,
    registered_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vehicles_pkey PRIMARY KEY (id),
    CONSTRAINT vehicles_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT vehicles_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT vehicles_kind_check CHECK (kind IN ('car', 'electric_car', 'motorbike', 'electric_motorbike', 'bicycle')),
    CONSTRAINT vehicles_status_check CHECK (status IN ('active', 'removed')),
    CONSTRAINT vehicles_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT vehicles_owner_user_id_fk FOREIGN KEY (owner_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX vehicles_unit_idx ON public.vehicles (tenant_id, unit_id);
CREATE UNIQUE INDEX vehicles_plate_uq ON public.vehicles (tenant_id, plate_no) WHERE status = 'active' AND plate_no IS NOT NULL;
ALTER TABLE public.vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.vehicles FORCE ROW LEVEL SECURITY;
CREATE POLICY vehicles_tenant_policy ON public.vehicles
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER vehicles_touch BEFORE UPDATE ON public.vehicles FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.access_cards (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    card_no text NOT NULL,
    kind text NOT NULL,
    holder_user_id text,
    holder_name text,
    unit_id uuid,
    vehicle_id uuid,
    status text NOT NULL,
    issued_at timestamp with time zone,
    valid_from date,
    valid_to date,
    monthly_fee bigint,
    issued_by_staff_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT access_cards_pkey PRIMARY KEY (id),
    CONSTRAINT access_cards_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT access_cards_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT access_cards_card_no_uq UNIQUE (tenant_id, card_no),
    CONSTRAINT access_cards_kind_check CHECK (kind IN ('resident', 'vehicle', 'temporary', 'worker', 'staff')),
    CONSTRAINT access_cards_status_check CHECK (status IN ('pending_issue', 'active', 'suspended', 'lost', 'expired', 'revoked')),
    CONSTRAINT access_cards_vehicle_check CHECK (kind <> 'vehicle' OR vehicle_id IS NOT NULL),
    CONSTRAINT access_cards_valid_check CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CONSTRAINT access_cards_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT access_cards_vehicle_id_fk FOREIGN KEY (tenant_id, vehicle_id) REFERENCES public.vehicles(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT access_cards_issued_by_staff_id_fk FOREIGN KEY (tenant_id, issued_by_staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT access_cards_holder_user_id_fk FOREIGN KEY (holder_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX access_cards_unit_idx ON public.access_cards (tenant_id, unit_id);
CREATE INDEX access_cards_vehicle_idx ON public.access_cards (tenant_id, vehicle_id);
ALTER TABLE public.access_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.access_cards FORCE ROW LEVEL SECURITY;
CREATE POLICY access_cards_tenant_policy ON public.access_cards
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER access_cards_touch BEFORE UPDATE ON public.access_cards FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER access_cards_transition BEFORE INSERT OR UPDATE OF status ON public.access_cards FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

-- ===== requests to the front desk =====

CREATE TABLE public.service_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    kind text NOT NULL,
    unit_id uuid NOT NULL,
    requester_user_id text NOT NULL,
    channel text NOT NULL,
    status text NOT NULL,
    priority text DEFAULT 'normal' NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    submitted_at timestamp with time zone,
    sla_due_at timestamp with time zone,
    assigned_staff_id uuid,
    decided_by_staff_id uuid,
    decided_at timestamp with time zone,
    decision_note text,
    fulfilled_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    cancel_reason text,
    fee_amount bigint DEFAULT 0 NOT NULL,
    debit_note_id uuid,
    rating smallint,
    rating_comment text,
    created_by_client_id text,
    idempotency_key text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT service_requests_pkey PRIMARY KEY (id),
    CONSTRAINT service_requests_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT service_requests_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT service_requests_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT service_requests_idempotency_uq UNIQUE (tenant_id, idempotency_key),
    CONSTRAINT service_requests_kind_check CHECK (kind IN ('card_issue', 'card_reissue', 'card_cancel', 'goods_move', 'resident_register', 'resident_update', 'resident_remove', 'other')),
    CONSTRAINT service_requests_channel_check CHECK (channel IN ('app', 'counter', 'hotline', 'agent')),
    CONSTRAINT service_requests_status_check CHECK (status IN ('draft', 'submitted', 'in_review', 'need_more_info', 'approved', 'rejected', 'fulfilled', 'cancelled')),
    CONSTRAINT service_requests_priority_check CHECK (priority IN ('low', 'normal', 'high')),
    CONSTRAINT service_requests_details_check CHECK (jsonb_typeof(details) = 'object'),
    CONSTRAINT service_requests_reject_check CHECK (status <> 'rejected' OR decision_note IS NOT NULL),
    CONSTRAINT service_requests_rating_check CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    CONSTRAINT service_requests_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_requests_requester_user_id_fk FOREIGN KEY (requester_user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT service_requests_assigned_staff_id_fk FOREIGN KEY (tenant_id, assigned_staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_requests_decided_by_staff_id_fk FOREIGN KEY (tenant_id, decided_by_staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_requests_debit_note_id_fk FOREIGN KEY (tenant_id, debit_note_id) REFERENCES public.debit_notes(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_requests_created_by_client_id_fk FOREIGN KEY (tenant_id, created_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX service_requests_unit_idx ON public.service_requests (tenant_id, unit_id, created_at DESC);
CREATE INDEX service_requests_open_idx ON public.service_requests (tenant_id, status, sla_due_at) WHERE status IN ('submitted', 'in_review', 'need_more_info', 'approved');
ALTER TABLE public.service_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.service_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY service_requests_tenant_policy ON public.service_requests
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER service_requests_touch BEFORE UPDATE ON public.service_requests FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER service_requests_transition BEFORE INSERT OR UPDATE OF status ON public.service_requests FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

CREATE TABLE public.service_request_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    service_request_id uuid NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    actor_kind text NOT NULL,
    actor_user_id text,
    actor_client_id text,
    from_status text,
    to_status text,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT service_request_events_pkey PRIMARY KEY (id),
    CONSTRAINT service_request_events_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT service_request_events_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT service_request_events_actor_check CHECK (actor_kind IN ('resident', 'staff', 'agent', 'system')),
    CONSTRAINT service_request_events_service_request_id_fk FOREIGN KEY (tenant_id, service_request_id) REFERENCES public.service_requests(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_request_events_actor_client_id_fk FOREIGN KEY (tenant_id, actor_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT service_request_events_actor_user_id_fk FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX service_request_events_request_idx ON public.service_request_events (tenant_id, service_request_id, occurred_at);
ALTER TABLE public.service_request_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.service_request_events FORCE ROW LEVEL SECURITY;
CREATE POLICY service_request_events_tenant_policy ON public.service_request_events
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER service_request_events_touch BEFORE UPDATE ON public.service_request_events FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER service_request_events_immutable BEFORE DELETE OR UPDATE ON public.service_request_events FOR EACH ROW EXECUTE FUNCTION public.app_append_only();
CREATE TRIGGER service_request_events_no_truncate BEFORE TRUNCATE ON public.service_request_events FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

-- ===== people who come to visit =====

CREATE TABLE public.visitor_passes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    unit_id uuid NOT NULL,
    host_user_id text NOT NULL,
    guest_name text NOT NULL,
    guest_phone text,
    guest_count integer DEFAULT 1 NOT NULL,
    purpose text NOT NULL,
    vehicle_plate_no text,
    visit_from timestamp with time zone NOT NULL,
    visit_to timestamp with time zone NOT NULL,
    qr_token text,
    status text NOT NULL,
    approved_by_staff_id uuid,
    created_by_client_id text,
    idempotency_key text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT visitor_passes_pkey PRIMARY KEY (id),
    CONSTRAINT visitor_passes_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT visitor_passes_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT visitor_passes_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT visitor_passes_idempotency_uq UNIQUE (tenant_id, idempotency_key),
    CONSTRAINT visitor_passes_purpose_check CHECK (purpose IN ('family_visit', 'delivery', 'service_provider', 'business', 'other')),
    CONSTRAINT visitor_passes_status_check CHECK (status IN ('pending_approval', 'approved', 'rejected', 'checked_in', 'checked_out', 'expired', 'cancelled')),
    CONSTRAINT visitor_passes_window_check CHECK (visit_to > visit_from),
    CONSTRAINT visitor_passes_guest_count_check CHECK (guest_count BETWEEN 1 AND 50),
    CONSTRAINT visitor_passes_qr_check CHECK (status NOT IN ('approved', 'checked_in', 'checked_out') OR qr_token IS NOT NULL),
    CONSTRAINT visitor_passes_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT visitor_passes_host_user_id_fk FOREIGN KEY (host_user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT visitor_passes_approved_by_staff_id_fk FOREIGN KEY (tenant_id, approved_by_staff_id) REFERENCES public.staff_profiles(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT visitor_passes_created_by_client_id_fk FOREIGN KEY (tenant_id, created_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX visitor_passes_unit_idx ON public.visitor_passes (tenant_id, unit_id, visit_from DESC);
CREATE UNIQUE INDEX visitor_passes_qr_uq ON public.visitor_passes (qr_token) WHERE qr_token IS NOT NULL;
ALTER TABLE public.visitor_passes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.visitor_passes FORCE ROW LEVEL SECURITY;
CREATE POLICY visitor_passes_tenant_policy ON public.visitor_passes
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER visitor_passes_touch BEFORE UPDATE ON public.visitor_passes FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER visitor_passes_transition BEFORE INSERT OR UPDATE OF status ON public.visitor_passes FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

CREATE TABLE public.access_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    gate_code text NOT NULL,
    direction text NOT NULL,
    credential_kind text NOT NULL,
    access_card_id uuid,
    visitor_pass_id uuid,
    vehicle_plate_no text,
    result text NOT NULL,
    deny_reason text,
    guard_user_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT access_events_pkey PRIMARY KEY (id),
    CONSTRAINT access_events_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT access_events_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT access_events_direction_check CHECK (direction IN ('in', 'out')),
    CONSTRAINT access_events_credential_check CHECK (credential_kind IN ('card', 'qr_pass', 'plate_recognition', 'manual')),
    CONSTRAINT access_events_result_check CHECK (result IN ('granted', 'denied')),
    CONSTRAINT access_events_reason_check CHECK (result <> 'denied' OR deny_reason IS NOT NULL),
    CONSTRAINT access_events_access_card_id_fk FOREIGN KEY (tenant_id, access_card_id) REFERENCES public.access_cards(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT access_events_visitor_pass_id_fk FOREIGN KEY (tenant_id, visitor_pass_id) REFERENCES public.visitor_passes(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT access_events_guard_user_id_fk FOREIGN KEY (guard_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX access_events_time_idx ON public.access_events (tenant_id, occurred_at DESC);
CREATE INDEX access_events_card_idx ON public.access_events (tenant_id, access_card_id, occurred_at DESC);
ALTER TABLE public.access_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.access_events FORCE ROW LEVEL SECURITY;
CREATE POLICY access_events_tenant_policy ON public.access_events
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER access_events_touch BEFORE UPDATE ON public.access_events FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER access_events_immutable BEFORE DELETE OR UPDATE ON public.access_events FOR EACH ROW EXECUTE FUNCTION public.app_append_only();
CREATE TRIGGER access_events_no_truncate BEFORE TRUNCATE ON public.access_events FOR EACH STATEMENT EXECUTE FUNCTION public.app_append_only();

-- ===== amenities =====

CREATE TABLE public.amenities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    zone_id uuid,
    name text NOT NULL,
    category text NOT NULL,
    booking_mode text DEFAULT 'time_slot' NOT NULL,
    areas text[] DEFAULT '{main}' NOT NULL,
    price bigint DEFAULT 0 NOT NULL,
    slot_minutes integer DEFAULT 60 NOT NULL,
    open_time time NOT NULL,
    close_time time NOT NULL,
    open_weekdays smallint[] DEFAULT '{1,2,3,4,5,6,7}' NOT NULL,
    max_advance_days integer DEFAULT 7 NOT NULL,
    cancel_before_hours integer DEFAULT 2 NOT NULL,
    weekly_quota_per_unit integer,
    max_guests integer DEFAULT 0 NOT NULL,
    rules_note text,
    status text DEFAULT 'active' NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT amenities_pkey PRIMARY KEY (id),
    CONSTRAINT amenities_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT amenities_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT amenities_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT amenities_category_check CHECK (category IN ('sport', 'pool', 'gym', 'bbq', 'community_room', 'playground', 'other')),
    CONSTRAINT amenities_mode_check CHECK (booking_mode IN ('time_slot', 'day_ticket', 'monthly_pass', 'walk_in')),
    CONSTRAINT amenities_status_check CHECK (status IN ('active', 'maintenance', 'closed')),
    CONSTRAINT amenities_hours_check CHECK (close_time > open_time AND slot_minutes BETWEEN 15 AND 1440 AND price >= 0),
    CONSTRAINT amenities_areas_check CHECK (cardinality(areas) >= 1),
    CONSTRAINT amenities_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX amenities_zone_idx ON public.amenities (tenant_id, zone_id);
ALTER TABLE public.amenities ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.amenities FORCE ROW LEVEL SECURITY;
CREATE POLICY amenities_tenant_policy ON public.amenities
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER amenities_touch BEFORE UPDATE ON public.amenities FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.amenity_closures (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    amenity_id uuid NOT NULL,
    from_ts timestamp with time zone NOT NULL,
    to_ts timestamp with time zone NOT NULL,
    reason text NOT NULL,
    created_by_user_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT amenity_closures_pkey PRIMARY KEY (id),
    CONSTRAINT amenity_closures_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT amenity_closures_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT amenity_closures_window_check CHECK (to_ts > from_ts),
    CONSTRAINT amenity_closures_amenity_id_fk FOREIGN KEY (tenant_id, amenity_id) REFERENCES public.amenities(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT amenity_closures_created_by_user_id_fk FOREIGN KEY (created_by_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX amenity_closures_amenity_idx ON public.amenity_closures (tenant_id, amenity_id, from_ts);
ALTER TABLE public.amenity_closures ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.amenity_closures FORCE ROW LEVEL SECURITY;
CREATE POLICY amenity_closures_tenant_policy ON public.amenity_closures
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER amenity_closures_touch BEFORE UPDATE ON public.amenity_closures FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.amenity_bookings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    amenity_id uuid NOT NULL,
    area_code text DEFAULT 'main' NOT NULL,
    unit_id uuid NOT NULL,
    booked_by_user_id text NOT NULL,
    start_at timestamp with time zone NOT NULL,
    end_at timestamp with time zone NOT NULL,
    guests integer DEFAULT 1 NOT NULL,
    status text NOT NULL,
    total_amount bigint DEFAULT 0 NOT NULL,
    qr_token text,
    cancelled_at timestamp with time zone,
    cancelled_by text,
    cancel_reason text,
    created_by_client_id text,
    idempotency_key text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT amenity_bookings_pkey PRIMARY KEY (id),
    CONSTRAINT amenity_bookings_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT amenity_bookings_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT amenity_bookings_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT amenity_bookings_idempotency_uq UNIQUE (tenant_id, idempotency_key),
    CONSTRAINT amenity_bookings_status_check CHECK (status IN ('pending_payment', 'confirmed', 'checked_in', 'completed', 'cancelled', 'no_show', 'expired')),
    CONSTRAINT amenity_bookings_window_check CHECK (end_at > start_at AND guests >= 1 AND total_amount >= 0),
    CONSTRAINT amenity_bookings_cancel_check CHECK (cancelled_by IS NULL OR cancelled_by IN ('resident', 'staff', 'agent', 'system')),
    CONSTRAINT amenity_bookings_no_overlap EXCLUDE USING gist (tenant_id WITH =, amenity_id WITH =, area_code WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (status IN ('pending_payment', 'confirmed', 'checked_in')),
    CONSTRAINT amenity_bookings_amenity_id_fk FOREIGN KEY (tenant_id, amenity_id) REFERENCES public.amenities(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT amenity_bookings_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT amenity_bookings_booked_by_user_id_fk FOREIGN KEY (booked_by_user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT amenity_bookings_created_by_client_id_fk FOREIGN KEY (tenant_id, created_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX amenity_bookings_unit_idx ON public.amenity_bookings (tenant_id, unit_id, start_at DESC);
CREATE INDEX amenity_bookings_amenity_idx ON public.amenity_bookings (tenant_id, amenity_id, start_at);
ALTER TABLE public.amenity_bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.amenity_bookings FORCE ROW LEVEL SECURITY;
CREATE POLICY amenity_bookings_tenant_policy ON public.amenity_bookings
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER amenity_bookings_touch BEFORE UPDATE ON public.amenity_bookings FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER amenity_bookings_transition BEFORE INSERT OR UPDATE OF status ON public.amenity_bookings FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

-- ===== renovation =====

CREATE TABLE public.construction_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    zone_id uuid,
    applies_to_unit_kind text,
    work_time_from time NOT NULL,
    work_time_to time NOT NULL,
    noisy_time_from time NOT NULL,
    noisy_time_to time NOT NULL,
    no_work_weekdays smallint[] DEFAULT '{}' NOT NULL,
    deposit_amount bigint NOT NULL,
    overtime_fee_per_hour bigint DEFAULT 0 NOT NULL,
    max_workers integer NOT NULL,
    max_duration_days integer NOT NULL,
    effective_from date NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT construction_policies_pkey PRIMARY KEY (id),
    CONSTRAINT construction_policies_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT construction_policies_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT construction_policies_hours_check CHECK (work_time_to > work_time_from AND noisy_time_to > noisy_time_from),
    CONSTRAINT construction_policies_limits_check CHECK (deposit_amount >= 0 AND max_workers > 0 AND max_duration_days > 0),
    CONSTRAINT construction_policies_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX construction_policies_zone_idx ON public.construction_policies (tenant_id, zone_id, effective_from DESC);
ALTER TABLE public.construction_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.construction_policies FORCE ROW LEVEL SECURITY;
CREATE POLICY construction_policies_tenant_policy ON public.construction_policies
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER construction_policies_touch BEFORE UPDATE ON public.construction_policies FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.construction_permits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    unit_id uuid NOT NULL,
    requester_user_id text NOT NULL,
    contractor_name text,
    self_performed boolean DEFAULT false NOT NULL,
    category text NOT NULL,
    scope_description text NOT NULL,
    planned_start date NOT NULL,
    planned_end date NOT NULL,
    actual_start date,
    actual_end date,
    status text NOT NULL,
    submitted_at timestamp with time zone,
    appraised_at timestamp with time zone,
    approved_at timestamp with time zone,
    reject_reason text,
    deposit_amount bigint DEFAULT 0 NOT NULL,
    deposit_status text DEFAULT 'none' NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT construction_permits_pkey PRIMARY KEY (id),
    CONSTRAINT construction_permits_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT construction_permits_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT construction_permits_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT construction_permits_category_check CHECK (category IN ('minor_repair', 'interior_fitout', 'renovation', 'structural_change')),
    CONSTRAINT construction_permits_status_check CHECK (status IN ('draft', 'submitted', 'appraised', 'approved', 'rejected', 'awaiting_deposit', 'in_progress', 'suspended', 'awaiting_acceptance', 'completed', 'cancelled', 'expired')),
    CONSTRAINT construction_permits_deposit_check CHECK (deposit_status IN ('none', 'pending', 'held', 'partially_refunded', 'refunded', 'forfeited')),
    CONSTRAINT construction_permits_dates_check CHECK (planned_end >= planned_start),
    CONSTRAINT construction_permits_reject_check CHECK (status <> 'rejected' OR reject_reason IS NOT NULL),
    CONSTRAINT construction_permits_unit_id_fk FOREIGN KEY (tenant_id, unit_id) REFERENCES public.units(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT construction_permits_requester_user_id_fk FOREIGN KEY (requester_user_id) REFERENCES public.users(id) ON DELETE RESTRICT
);
CREATE INDEX construction_permits_unit_idx ON public.construction_permits (tenant_id, unit_id, created_at DESC);
ALTER TABLE public.construction_permits ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.construction_permits FORCE ROW LEVEL SECURITY;
CREATE POLICY construction_permits_tenant_policy ON public.construction_permits
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER construction_permits_touch BEFORE UPDATE ON public.construction_permits FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER construction_permits_transition BEFORE INSERT OR UPDATE OF status ON public.construction_permits FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

-- ===== what residents are told and what the agents may read =====

CREATE TABLE public.handbook_articles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    parent_id uuid,
    zone_id uuid,
    seq integer DEFAULT 0 NOT NULL,
    title text NOT NULL,
    body_md text DEFAULT '' NOT NULL,
    audience text[] DEFAULT '{resident}' NOT NULL,
    language text DEFAULT 'vi' NOT NULL,
    status text DEFAULT 'published' NOT NULL,
    effective_from date DEFAULT current_date NOT NULL,
    effective_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT handbook_articles_pkey PRIMARY KEY (id),
    CONSTRAINT handbook_articles_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT handbook_articles_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT handbook_articles_status_check CHECK (status IN ('draft', 'published')),
    CONSTRAINT handbook_articles_audience_check CHECK (audience <@ ARRAY['resident', 'staff', 'management']::text[] AND cardinality(audience) >= 1),
    CONSTRAINT handbook_articles_window_check CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT handbook_articles_parent_id_fk FOREIGN KEY (tenant_id, parent_id) REFERENCES public.handbook_articles(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT handbook_articles_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX handbook_articles_parent_idx ON public.handbook_articles (tenant_id, parent_id, seq);
ALTER TABLE public.handbook_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.handbook_articles FORCE ROW LEVEL SECURITY;
CREATE POLICY handbook_articles_tenant_policy ON public.handbook_articles
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER handbook_articles_touch BEFORE UPDATE ON public.handbook_articles FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.policy_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    title text NOT NULL,
    kind text NOT NULL,
    version text NOT NULL,
    body_md text DEFAULT '' NOT NULL,
    zone_id uuid,
    unit_kind text,
    audience text[] DEFAULT '{resident}' NOT NULL,
    language text DEFAULT 'vi' NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT policy_documents_pkey PRIMARY KEY (id),
    CONSTRAINT policy_documents_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT policy_documents_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT policy_documents_code_uq UNIQUE (tenant_id, code, version),
    CONSTRAINT policy_documents_kind_check CHECK (kind IN ('terms_of_use', 'privacy_policy', 'building_rules', 'construction_rules', 'amenity_rules', 'fee_table', 'faq')),
    CONSTRAINT policy_documents_audience_check CHECK (audience <@ ARRAY['resident', 'staff', 'management']::text[] AND cardinality(audience) >= 1),
    CONSTRAINT policy_documents_window_check CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT policy_documents_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX policy_documents_kind_idx ON public.policy_documents (tenant_id, kind, effective_from DESC);
ALTER TABLE public.policy_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.policy_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY policy_documents_tenant_policy ON public.policy_documents
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER policy_documents_touch BEFORE UPDATE ON public.policy_documents FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.announcements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    kind text NOT NULL,
    title text NOT NULL,
    summary text,
    body_md text NOT NULL,
    is_important boolean DEFAULT false NOT NULL,
    status text NOT NULL,
    publish_at timestamp with time zone,
    published_at timestamp with time zone,
    expire_at timestamp with time zone,
    effective_from timestamp with time zone,
    effective_to timestamp with time zone,
    zone_ids uuid[] DEFAULT '{}' NOT NULL,
    building_ids uuid[] DEFAULT '{}' NOT NULL,
    author_user_id text,
    drafted_by text DEFAULT 'staff' NOT NULL,
    drafted_by_client_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT announcements_pkey PRIMARY KEY (id),
    CONSTRAINT announcements_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT announcements_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT announcements_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT announcements_kind_check CHECK (kind IN ('news', 'bulletin', 'urgent_notice', 'outage_notice', 'event_notice', 'fee_notice')),
    CONSTRAINT announcements_status_check CHECK (status IN ('draft', 'scheduled', 'published', 'archived')),
    CONSTRAINT announcements_drafted_check CHECK (drafted_by IN ('staff', 'agent') AND (drafted_by = 'agent') = (drafted_by_client_id IS NOT NULL)),
    CONSTRAINT announcements_window_check CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from),
    CONSTRAINT announcements_published_check CHECK (status NOT IN ('published', 'archived') OR published_at IS NOT NULL),
    CONSTRAINT announcements_author_user_id_fk FOREIGN KEY (author_user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT announcements_drafted_by_client_id_fk FOREIGN KEY (tenant_id, drafted_by_client_id) REFERENCES public.integration_clients(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX announcements_status_idx ON public.announcements (tenant_id, status, published_at DESC);
ALTER TABLE public.announcements ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.announcements FORCE ROW LEVEL SECURITY;
CREATE POLICY announcements_tenant_policy ON public.announcements
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER announcements_touch BEFORE UPDATE ON public.announcements FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
CREATE TRIGGER announcements_transition BEFORE INSERT OR UPDATE OF status ON public.announcements FOR EACH ROW EXECUTE FUNCTION public.app_enforce_transition();

-- ===== a request gets its due times from the policy that applies to it =====
-- Done where the data lives, so every way a ticket is created (app, chat, Reception, desk) is held to it.

CREATE FUNCTION public.app_assign_sla() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE p public.sla_policies;
BEGIN
  IF NEW.sla_policy_id IS NULL AND NEW.management_unit_id IS NOT NULL AND NEW.category_id IS NOT NULL THEN
    SELECT * INTO p FROM public.sla_policies s
    WHERE s.tenant_id = NEW.tenant_id AND s.domain_id = NEW.domain_id AND s.management_unit_id = NEW.management_unit_id
      AND s.category_id = NEW.category_id AND s.request_kind = NEW.request_kind AND s.priority = COALESCE(NEW.priority, 'normal')
      AND s.effective_from <= NEW.created_at AND (s.effective_to IS NULL OR s.effective_to > NEW.created_at)
    ORDER BY s.version_no DESC LIMIT 1;
    IF FOUND THEN
      NEW.sla_policy_id := p.id;
      NEW.response_due_at := NEW.created_at + make_interval(mins => p.response_minutes);
      NEW.resolution_due_at := NEW.created_at + make_interval(mins => p.resolution_minutes);
    END IF;
  END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER tickets_sla_assign BEFORE INSERT OR UPDATE OF management_unit_id, category_id, priority ON public.tickets FOR EACH ROW EXECUTE FUNCTION public.app_assign_sla();
