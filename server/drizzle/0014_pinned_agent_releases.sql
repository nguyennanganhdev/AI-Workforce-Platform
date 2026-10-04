-- New sessions choose the newest published version. Existing sessions retain their
-- approved version until BQL/admin explicitly revokes that agent's releases.
DROP INDEX "agent_releases_partial_0";
--> statement-breakpoint
CREATE UNIQUE INDEX "agent_releases_partial_0" ON "agent_releases"("version_id")
WHERE status='published' AND revoked_at IS NULL;
