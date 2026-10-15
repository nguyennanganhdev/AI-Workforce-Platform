-- One Domain tenant can serve several projects. A document without a site is unassigned,
-- never an implicit policy for every Ocean Park. Keep old document/chunk IDs and vectors.
ALTER TABLE public.sites ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE public.vh_knowledge_documents ADD COLUMN site_id uuid;
UPDATE public.vh_knowledge_documents d SET site_id=z.site_id
FROM public.zones z WHERE z.id=d.zone_id AND z.tenant_id=d.tenant_id;
UPDATE public.vh_knowledge_documents d SET site_id=s.id
FROM public.sites s
WHERE d.site_id IS NULL AND s.tenant_id=d.tenant_id
  AND (SELECT count(*) FROM public.sites candidate WHERE candidate.tenant_id=d.tenant_id)=1;
ALTER TABLE public.vh_knowledge_documents ADD CONSTRAINT vh_knowledge_documents_site_fk
  FOREIGN KEY (tenant_id,site_id) REFERENCES public.sites(tenant_id,id) ON DELETE RESTRICT;
CREATE INDEX vh_knowledge_documents_site_idx ON public.vh_knowledge_documents(tenant_id,site_id,audience);
