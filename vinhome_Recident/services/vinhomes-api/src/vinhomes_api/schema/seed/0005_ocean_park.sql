-- The demo site becomes Vinhomes Ocean Park 1, with the areas and buildings the resident
-- knowledge (Data-Vinhome) is written for. Knowledge is published to these scopes:
--   00-do-thi            -> the site
--   <operator>/<area>    -> the zone whose code is the area folder
--   .../<building>       -> the building whose code is the building folder
-- Masteri Waterfront is run by Masterise Property Management, not Vinhomes: its zone and
-- buildings exist so its documents have a scope, and nobody lives there in the demo.
BEGIN;

-- Stable ids that are also valid RFC 4122 UUIDs: the knowledge service validates them strictly.
CREATE OR REPLACE FUNCTION pg_temp.seed_id(name text) RETURNS uuid LANGUAGE sql IMMUTABLE AS $$
  SELECT (substr(h, 1, 12) || '5' || substr(h, 14, 3) || 'a' || substr(h, 18, 15))::uuid FROM (SELECT md5(name) AS h) x
$$;

UPDATE sites SET code = 'ocean-park-1', name = 'Vinhomes Ocean Park 1', address = 'Gia Lâm, Hà Nội'
WHERE id = '66666666-6666-5666-a666-666666666666' AND code = 'local-site';

INSERT INTO zones (id, tenant_id, site_id, code, name, status)
SELECT pg_temp.seed_id('ocean-park-zone:' || z.code), '11111111-1111-5111-a111-111111111111',
       '66666666-6666-5666-a666-666666666666', z.code, z.name, 'active'
FROM (VALUES ('sapphire', 'Sapphire'), ('pavilion', 'Pavilion'), ('zenpark', 'Zenpark'),
             ('hai-au', 'Hải Âu'), ('ngoc-trai', 'Ngọc Trai'), ('san-ho', 'San Hô'), ('sao-bien', 'Sao Biển'),
             ('masteri-waterfront', 'Masteri Waterfront')) AS z(code, name)
ON CONFLICT DO NOTHING;

-- The demo resident's building is S1.01 in Sapphire.
UPDATE buildings SET code = 'S1.01', name = 'Sapphire 1 - S1.01', zone_id = pg_temp.seed_id('ocean-park-zone:sapphire')
WHERE id = '77777777-7777-5777-a777-777777777777' AND code = 'local-building';

INSERT INTO buildings (id, tenant_id, site_id, zone_id, code, name, status)
SELECT pg_temp.seed_id('ocean-park-building:' || b.code), '11111111-1111-5111-a111-111111111111',
       '66666666-6666-5666-a666-666666666666', pg_temp.seed_id('ocean-park-zone:' || b.zone), b.code, b.name, 'active'
FROM (VALUES ('S1.02', 'sapphire', 'Sapphire 1 - S1.02'), ('S2.01', 'sapphire', 'Sapphire 2 - S2.01'),
             ('S2.05', 'sapphire', 'Sapphire 2 - S2.05'), ('P1', 'pavilion', 'Pavilion P1'), ('P2', 'pavilion', 'Pavilion P2'),
             ('R1.02', 'zenpark', 'Zenpark R1.02'), ('R1.03', 'zenpark', 'Zenpark R1.03'),
             ('M1', 'masteri-waterfront', 'Masteri Waterfront M1'), ('M2', 'masteri-waterfront', 'Masteri Waterfront M2'),
             ('M3', 'masteri-waterfront', 'Masteri Waterfront M3'), ('H1', 'masteri-waterfront', 'Masteri Waterfront H1'),
             ('H2', 'masteri-waterfront', 'Masteri Waterfront H2'), ('H3', 'masteri-waterfront', 'Masteri Waterfront H3')) AS b(code, zone, name)
ON CONFLICT DO NOTHING;

INSERT INTO access_scopes (id, tenant_id, kind, site_id)
SELECT pg_temp.seed_id('ocean-park-scope:site'), tenant_id, 'site', id FROM sites s
WHERE s.id = '66666666-6666-5666-a666-666666666666'
  AND NOT EXISTS (SELECT 1 FROM access_scopes a WHERE a.kind = 'site' AND a.site_id = s.id);

INSERT INTO access_scopes (id, tenant_id, kind, zone_id)
SELECT pg_temp.seed_id('ocean-park-scope:zone:' || z.code), z.tenant_id, 'zone', z.id FROM zones z
WHERE z.site_id = '66666666-6666-5666-a666-666666666666'
  AND NOT EXISTS (SELECT 1 FROM access_scopes a WHERE a.kind = 'zone' AND a.zone_id = z.id);

INSERT INTO access_scopes (id, tenant_id, kind, building_id)
SELECT pg_temp.seed_id('ocean-park-scope:building:' || b.code), b.tenant_id, 'building', b.id FROM buildings b
WHERE b.site_id = '66666666-6666-5666-a666-666666666666'
  AND NOT EXISTS (SELECT 1 FROM access_scopes a WHERE a.kind = 'building' AND a.building_id = b.id);

COMMIT;
