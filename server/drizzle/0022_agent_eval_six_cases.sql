-- A suite is six generated cases and a run passes on four of them (was: exactly four, all four).
ALTER TABLE vh_agent_eval_cases DROP CONSTRAINT IF EXISTS vh_agent_eval_cases_ordinal_check;
--> statement-breakpoint
ALTER TABLE vh_agent_eval_cases ADD CONSTRAINT vh_agent_eval_cases_ordinal_check CHECK(ordinal BETWEEN 1 AND 6);
--> statement-breakpoint
ALTER TABLE vh_agent_eval_case_results DROP CONSTRAINT IF EXISTS vh_agent_eval_case_results_ordinal_check;
--> statement-breakpoint
ALTER TABLE vh_agent_eval_case_results ADD CONSTRAINT vh_agent_eval_case_results_ordinal_check CHECK(ordinal BETWEEN 1 AND 6);
