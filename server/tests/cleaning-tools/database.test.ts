import { afterAll, beforeAll, expect, test } from "bun:test";
import { createDbCleaningWorkOrderCheck } from "../../src/cleaning-tools/adapters/database";
import {
  technicalToolsTestDatabase,
  type TestDatabase,
  DATABASE_SETUP_TIMEOUT_MS,
} from "../technical-tools/support/database";
import { TENANT, BUILDING } from "../technical-tools/fixtures/world";
import { WORK } from "../technical-tools/fixtures/work-orders";

let db: TestDatabase;
const categoryId = "91111111-1111-4111-8111-111111111111";
const job = WORK.ac;
beforeAll(async () => {
  db = await technicalToolsTestDatabase({ isolated: true });
  // Fixture data only, inside an isolated PGlite database with existing migrations.
  await db.rows("RESET ROLE");
  await db.rows(`INSERT INTO service_categories(tenant_id,id,code,name,enabled)
    VALUES('${TENANT.vinhomes}','${categoryId}','cleaning','Vệ sinh',true)`);
  await db.rows(
    `UPDATE work_orders SET category_id='${categoryId}',required_specialty_id='${categoryId}' WHERE id='${job.workOrderId}'`,
  );
  await db.rows(
    "GRANT SELECT ON service_categories TO technical_tools_runtime",
  );
  await db.rows("SET ROLE technical_tools_runtime");
}, DATABASE_SETUP_TIMEOUT_MS);
afterAll(async () => {
  await db?.close();
});

test("category check refuses technical work, other building and tenant", async () => {
  const check = createDbCleaningWorkOrderCheck(db.database);
  expect(await check(TENANT.vinhomes, job.buildingId, job.workOrderId)).toBe(
    true,
  );
  expect(
    await check(TENANT.vinhomes, WORK.leak.buildingId, WORK.leak.workOrderId),
  ).toBe(false);
  expect(await check(TENANT.vinhomes, BUILDING.x1, job.workOrderId)).toBe(
    false,
  );
  expect(await check(TENANT.other, job.buildingId, job.workOrderId)).toBe(
    false,
  );
});
