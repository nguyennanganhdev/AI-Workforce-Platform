-- Knowledge the assistants answer from: documents cut into passages, each passage with its search words and its
-- embedding. Reception searches it for a resident (POST /internal/knowledge/search); staff agents will later.
--
-- A document is written for an audience ('resident' or 'staff') and for a place: the whole site (zone_id and
-- building_ids empty), one zone, or some buildings of a zone. A resident only ever gets resident documents of
-- the site, of the zone they live in and of their building. A tenant is one site here, so the site has no column.
--
-- The tables carry the domain's vh_ prefix: knowledge_documents and knowledge_chunks are the platform's names,
-- which this schema keeps out (tests/test_schema_contract.py).
--
-- Ids are given by whoever prepares the documents and are kept on every reload, so an answer's citation stays
-- valid. version_id names the edition of the document the passages were cut from.
--
-- The embedding is a pgvector column of 1536 numbers (OpenAI text-embedding-3-large, dimensions=1536); the search
-- ranks by cosine distance (<=>) in SQL. The extension is not trusted: only a superuser can create it. In the
-- package's own PostgreSQL (image pgvector/pgvector) the owner is one, so the line below creates it. On another
-- PostgreSQL its administrator installs pgvector and runs "create extension vector" in this database before
-- `migrate` (managed services list it as "vector"); the line below then does nothing and a plain owner migrates.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE public.vh_knowledge_documents (
    id uuid NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    code text NOT NULL,
    version_id uuid NOT NULL,
    title text NOT NULL,
    category text NOT NULL,
    audience text NOT NULL,
    zone_id uuid,
    building_ids uuid[],
    unverified boolean DEFAULT false NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_knowledge_documents_pkey PRIMARY KEY (id),
    CONSTRAINT vh_knowledge_documents_tenant_key_uq UNIQUE (tenant_id, id),
    CONSTRAINT vh_knowledge_documents_code_uq UNIQUE (tenant_id, code),
    CONSTRAINT vh_knowledge_documents_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT vh_knowledge_documents_zone_id_fk FOREIGN KEY (tenant_id, zone_id) REFERENCES public.zones(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT vh_knowledge_documents_audience_check CHECK (audience = ANY (ARRAY['resident'::text, 'staff'::text])),
    -- Buildings narrow a zone; an empty list would hide the document from everyone.
    CONSTRAINT vh_knowledge_documents_buildings_check CHECK (building_ids IS NULL OR (zone_id IS NOT NULL AND cardinality(building_ids) >= 1))
);
ALTER TABLE public.vh_knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.vh_knowledge_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_knowledge_documents_tenant_policy ON public.vh_knowledge_documents
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER vh_knowledge_documents_touch BEFORE UPDATE ON public.vh_knowledge_documents FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();

CREATE TABLE public.vh_knowledge_chunks (
    id uuid NOT NULL,
    tenant_id uuid DEFAULT (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid NOT NULL,
    document_id uuid NOT NULL,
    ordinal integer NOT NULL,
    heading_path text,
    text_content text NOT NULL,
    text_hash text NOT NULL,
    token_count integer NOT NULL,
    search_tsv tsvector NOT NULL,
    embedding vector(1536),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vh_knowledge_chunks_pkey PRIMARY KEY (id),
    -- Deferred: a reload may renumber the passages of a document.
    CONSTRAINT vh_knowledge_chunks_ordinal_uq UNIQUE (document_id, ordinal) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT vh_knowledge_chunks_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
    CONSTRAINT vh_knowledge_chunks_document_id_fk FOREIGN KEY (tenant_id, document_id) REFERENCES public.vh_knowledge_documents(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX vh_knowledge_chunks_search_idx ON public.vh_knowledge_chunks USING gin (search_tsv);
-- Nearest passages over the whole table. The search does not go through it: it scores every passage of the
-- resident's place exactly (knowledge.search says why).
CREATE INDEX vh_knowledge_chunks_embedding_idx ON public.vh_knowledge_chunks USING hnsw (embedding vector_cosine_ops);
ALTER TABLE public.vh_knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE ONLY public.vh_knowledge_chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY vh_knowledge_chunks_tenant_policy ON public.vh_knowledge_chunks
    USING ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid))
    WITH CHECK ((tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid));
CREATE TRIGGER vh_knowledge_chunks_touch BEFORE UPDATE ON public.vh_knowledge_chunks FOR EACH ROW EXECUTE FUNCTION public.app_touch_updated_at();
