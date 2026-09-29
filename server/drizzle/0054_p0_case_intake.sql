-- P0 only; legacy candidate state must be exported/mapped before removing its tables.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM vh_issue_candidate)
     OR EXISTS (SELECT 1 FROM vh_issue_relation)
     OR EXISTS (SELECT 1 FROM vh_resident_report WHERE issue_candidate_id IS NOT NULL) THEN
    RAISE EXCEPTION '0054 requires empty legacy issue candidates/links; migrate case state first';
  END IF;
END $$;
--> statement-breakpoint
DROP POLICY "vh_issue_candidate_tenant_policy" ON "vh_issue_candidate" CASCADE;--> statement-breakpoint
DROP TABLE "vh_issue_candidate" CASCADE;--> statement-breakpoint
DROP POLICY "vh_issue_relation_tenant_policy" ON "vh_issue_relation" CASCADE;--> statement-breakpoint
DROP TABLE "vh_issue_relation" CASCADE;--> statement-breakpoint
ALTER TABLE "vh_resident_report" DROP CONSTRAINT IF EXISTS "vh_resident_report_uq_0";--> statement-breakpoint
ALTER TABLE "vh_resident_report" DROP CONSTRAINT IF EXISTS "vh_resident_report_fk_3";
--> statement-breakpoint
DROP INDEX IF EXISTS "vh_resident_report_ix_1";--> statement-breakpoint
ALTER TABLE "vh_case" ADD COLUMN "intake_state_json" jsonb DEFAULT '{"issueCandidates":[]}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "vh_resident_report" DROP COLUMN "issue_candidate_id";--> statement-breakpoint
ALTER TABLE "vh_case" ADD CONSTRAINT "vh_case_intake_state_ck" CHECK (jsonb_typeof("vh_case"."intake_state_json") = 'object' AND jsonb_typeof("vh_case"."intake_state_json"->'issueCandidates') = 'array');