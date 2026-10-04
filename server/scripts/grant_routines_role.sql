-- Execute as database owner after creating a LOGIN role named vinhomes_routines.
-- The schedule service (src/room-routines): the platform's routine store and its queue, nothing else.
-- The business API decides who may schedule; this role keeps the rows and stays under tenant row security.
GRANT USAGE ON SCHEMA public TO vinhomes_routines;
GRANT SELECT ON channels, channel_memberships, channel_agents TO vinhomes_routines;
GRANT SELECT, INSERT, UPDATE, DELETE ON routines, routine_runs, work_items TO vinhomes_routines;
GRANT SELECT, INSERT, UPDATE ON routine_sweeps TO vinhomes_routines;
