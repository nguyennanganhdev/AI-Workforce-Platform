-- Recoverable personal chat removal; requests and their evidence remain accessible.
ALTER TABLE public.channel_memberships ADD COLUMN archived_at timestamptz;
-- Only curated public stages; no prompts, model reasoning or tool arguments.
ALTER TABLE public.delegations ADD COLUMN resident_progress jsonb NOT NULL DEFAULT '[]'::jsonb;
