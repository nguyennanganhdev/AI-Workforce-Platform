-- Bind new platform writes to their arguments as well as ticket and tool. Historical receipts stay readable.
ALTER TABLE public.platform_operations ADD COLUMN request_hash text;
