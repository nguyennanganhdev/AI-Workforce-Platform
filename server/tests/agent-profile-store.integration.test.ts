import { afterAll, afterEach, describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { and, eq, sql } from "drizzle-orm";
import { authFromConfiguration } from "../src/agents/auth-header";
import type { FactoryConfiguration } from "../../agent-factory/src/contracts.js";
import {
  AgentNotFoundError,
  AgentNotManageableError,
  type AgentProfileStore,
  ConstructionConflictError,
  ConstructionDeletedError,
  createAgentProfileStore,
  GeneratedConfigurationImmutableError,
  ManagedAgentUnavailableError,
  ProtectedAgentError,
} from "../src/agents/profile-store";
import type {
  AgentActor,
  AgentProfile,
  CreateAgentInput,
} from "../src/agents/profile-types";
import { DEPLOYMENT_ROUTES } from "../src/computer/deployment-routes";
import { createDatabase } from "../src/db/client";
import {
  agentPreferences,
  agentProfiles,
  agents,
  channelAgents,
  channels,
  deploymentPackages,
  intelligenceChannelMappings,
  users,
} from "../src/db/schema";
import { compileRecorded } from "../../agent-factory/tests/fixtures/factory-intent";
import { TEST_POOL, testDatabaseUrl } from "./support/database";

const databaseUrl = testDatabaseUrl();
const database = createDatabase(databaseUrl, TEST_POOL);
const managedAgentAgUiUrl = new URL("https://managed.example.test/ag-ui");
const store: AgentProfileStore = createAgentProfileStore(
  database,
  managedAgentAgUiUrl,
);
const testPrefix = `agent-profile-store-${randomUUID()}`;
const createdUserIds: string[] = [];
const createdAgentIds: string[] = [];
const createdChannelIds: string[] = [];
const createdPackageIds: string[] = [];

afterEach(async () => {
  for (const channelId of createdChannelIds.splice(0)) {
    await database.delete(channels).where(eq(channels.id, channelId));
  }
  for (const agentId of createdAgentIds.splice(0)) {
    await database.delete(agents).where(eq(agents.id, agentId));
  }
  for (const packageId of createdPackageIds.splice(0)) {
    await database
      .delete(deploymentPackages)
      .where(eq(deploymentPackages.id, packageId));
  }
  for (const userId of createdUserIds.splice(0)) {
    await database.delete(users).where(eq(users.id, userId));
  }
});

afterAll(async () => {
  await database.$client.close();
});

function id(kind: string) {
  return `${testPrefix}-${kind}-${randomUUID()}`;
}

async function createUser(role: AgentActor["role"] = "user") {
  const userId = id("user");
  await database.insert(users).values({
    id: userId,
    email: `${userId}@example.test`,
    name: "Profile Store Test User",
  });
  createdUserIds.push(userId);
  return { id: userId, role } satisfies AgentActor;
}

async function createPackage() {
  const [deploymentPackage] = await database
    .insert(deploymentPackages)
    .values({
      tenantId: id("tenant"),
      sourcePath: "test/profile-store",
      checksum: randomUUID(),
    })
    .returning();
  if (!deploymentPackage) throw new Error("Expected deployment package.");
  createdPackageIds.push(deploymentPackage.id);
  return deploymentPackage;
}

async function createProfileFixture(options: {
  owner: AgentActor | null;
  visibility?: "public" | "private";
  packageId?: string;
  name?: string;
  title?: string;
  roleDescription?: string;
  avatarSeed?: string;
  configuration?: Record<string, unknown>;
}) {
  const agentId = id("seed-agent");
  const name = options.name ?? `Seed ${randomUUID()}`;
  const title = options.title ?? "Seed Assistant";
  const roleDescription = options.roleDescription ?? "Helps test profiles.";
  const avatarSeed = options.avatarSeed ?? `avatar-${randomUUID()}`;
  await database.insert(agents).values({
    id: agentId,
    name,
    type: "remote_ag_ui",
    configuration: options.configuration ?? {
      endpoint: "https://seed.example.test/ag-ui",
    },
    packageId: options.packageId,
  });
  createdAgentIds.push(agentId);
  await database.insert(agentProfiles).values({
    agentId,
    ownerUserId: options.owner?.id ?? null,
    title,
    roleDescription,
    avatarSeed,
    visibility: options.visibility ?? "private",
  });
  return { agentId, name, title, roleDescription, avatarSeed };
}

async function profileById(actor: AgentActor, agentId: string) {
  const profile = await store.get(actor, agentId);
  if (!profile) throw new Error(`Expected visible profile ${agentId}.`);
  return profile;
}

function expectListed(
  profiles: AgentProfile[],
  agentId: string,
  expected: boolean,
) {
  expect(profiles.some((profile) => profile.id === agentId)).toBe(expected);
}

function deferred() {
  let resolve!: () => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<void>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function waitForMutationBlock(
  applicationName: string,
  mutationSettled: () => boolean,
) {
  const deadline = Date.now() + 3_000;
  while (Date.now() < deadline) {
    const blockedSessions = await database.execute(sql`
      SELECT pid
      FROM pg_stat_activity
      WHERE application_name = ${applicationName}
        AND cardinality(pg_blocking_pids(pid)) > 0
      LIMIT 1
    `);
    if (blockedSessions.length > 0) return true;
    if (mutationSettled()) return false;
  }
  throw new Error(`Timed out observing blocked session ${applicationName}.`);
}

async function racePackageAttachment(
  agentId: string,
  packageId: string,
  mutate: (namedStore: AgentProfileStore) => Promise<unknown>,
) {
  const applicationName = `profile_store_lock_${randomUUID()}`;
  const namedDatabaseUrl = new URL(databaseUrl);
  namedDatabaseUrl.searchParams.set("application_name", applicationName);
  const namedDatabase = createDatabase(namedDatabaseUrl.toString(), TEST_POOL);
  const namedStore = createAgentProfileStore(
    namedDatabase,
    managedAgentAgUiUrl,
  );
  const writeAcquired = deferred();
  const releaseAttachment = deferred();
  const attachment = database.transaction(async (transaction) => {
    await transaction
      .update(agents)
      .set({ packageId })
      .where(eq(agents.id, agentId));
    writeAcquired.resolve();
    await releaseAttachment.promise;
  });
  void attachment.catch(writeAcquired.reject);

  try {
    await writeAcquired.promise;
    let settled = false;
    const outcomePromise = mutate(namedStore).then(
      (value) => {
        settled = true;
        return { status: "fulfilled", value } as const;
      },
      (reason: unknown) => {
        settled = true;
        return { reason, status: "rejected" } as const;
      },
    );
    const blocked = await waitForMutationBlock(applicationName, () => settled);
    releaseAttachment.resolve();
    await attachment;
    return { blocked, outcome: await outcomePromise };
  } finally {
    releaseAttachment.resolve();
    await attachment.catch(() => undefined);
    await namedDatabase.$client.close();
  }
}

/**
 * The stored row behind a coworker, proven to exist before anything reads it.
 *
 * Asserted here rather than at each call site because a missing row and a missing field are
 * different failures that an optional chain would collapse into the same one — "systemPrompt is
 * undefined" reads as a prompt that was not written when it may be a coworker that is not there.
 */
async function agentRow(agentId: string): Promise<{
  type: string;
  configuration: { systemPrompt?: string; endpoint?: string };
}> {
  const [row] = await database
    .select({ type: agents.type, configuration: agents.configuration })
    .from(agents)
    .where(eq(agents.id, agentId));
  if (!row) throw new Error(`no agents row for ${agentId}`);
  return {
    type: row.type,
    configuration: (row.configuration ?? {}) as {
      systemPrompt?: string;
      endpoint?: string;
    },
  };
}

describe("agent profile store integration", () => {
  test("refuses to create a coworker with no endpoint when this deployment has no managed Bot", async () => {
    const owner = await createUser();
    const withoutManaged = createAgentProfileStore(database, undefined);

    await expect(
      withoutManaged.create(owner, {
        name: "No Endpoint",
        title: "Needs an address",
        roleDescription: "Should not land on a missing Bot.",
        visibility: "private",
      }),
    ).rejects.toBeInstanceOf(ManagedAgentUnavailableError);
  });

  /**
   * The coworker with nowhere to send it, and the instruction it actually runs on.
   *
   * `registeredAgentFromRow` gives a `built_in` agent its `configuration.systemPrompt` and NO
   * standing role message, so that column is the whole of what such a coworker is ever told —
   * `agentProfiles.roleDescription` never reaches it. These two tests exist because the pair can
   * drift silently: creating writes both, and an edit that wrote only the profile left every screen
   * showing new instructions while the Bot went on following the old ones, for good, with nothing
   * anywhere to say so.
   */
  test("creates a coworker that runs here when there is nowhere to send it", async () => {
    const owner = await createUser();
    const withoutManaged = createAgentProfileStore(database, undefined);

    const created = await withoutManaged.create(owner, {
      name: "Runs Here",
      title: "Everyday Work",
      roleDescription: "Answer from the ledger and quote the line you used.",
      visibility: "private",
      systemPrompt: "Answer from the ledger and quote the line you used.",
    });
    createdAgentIds.push(created.id);

    const row = await agentRow(created.id);
    expect(row.type).toBe("built_in");
    expect(row.configuration.systemPrompt).toBe(
      "Answer from the ledger and quote the line you used.",
    );
    // No address was given and none was invented; that is what makes it built_in rather than remote.
    expect(row.configuration.endpoint).toBeUndefined();
  });

  test("an edit moves the instruction such a coworker actually runs on", async () => {
    const owner = await createUser();
    const withoutManaged = createAgentProfileStore(database, undefined);
    const created = await withoutManaged.create(owner, {
      name: "Runs Here",
      title: "Everyday Work",
      roleDescription: "The first instruction.",
      visibility: "private",
      systemPrompt: "The first instruction.",
    });
    createdAgentIds.push(created.id);

    await withoutManaged.update(owner, created.id, {
      name: "Runs Here",
      title: "Everyday Work",
      roleDescription: "The second instruction, which must be the live one.",
      visibility: "private",
    });

    const row = await agentRow(created.id);
    expect(row.type).toBe("built_in");
    expect(row.configuration.systemPrompt).toBe(
      "The second instruction, which must be the live one.",
    );
    // And the profile every screen reads agrees with it, rather than only the profile moving.
    expect((await profileById(owner, created.id)).roleDescription).toBe(
      "The second instruction, which must be the live one.",
    );
  });

  /**
   * The other half of the same rule: a remote coworker must not acquire a prompt it never had.
   *
   * Its instruction travels as the standing role message built from the profile, so a `systemPrompt`
   * appearing in its configuration would be a second source for the same thing — and the one the
   * runtime prefers for a `built_in` row, which is what this coworker would look like if its type
   * ever changed.
   */
  test("an edit never gives a coworker at its own address a system prompt", async () => {
    const owner = await createUser();
    const source = await createProfileFixture({
      owner,
      visibility: "private",
      configuration: { endpoint: "https://remote.example.test/ag-ui" },
    });

    await store.update(owner, source.agentId, {
      name: "Still Remote",
      title: "Elsewhere",
      roleDescription: "Edited, and it still runs at its own address.",
      visibility: "private",
      endpoint: "https://remote.example.test/ag-ui",
    });

    const row = await agentRow(source.agentId);
    expect(row.type).toBe("remote_ag_ui");
    expect(row.configuration.systemPrompt).toBeUndefined();
  });

  test("lets an owner and admin get and list a private profile but hides it from another user", async () => {
    const owner = await createUser();
    const other = await createUser();
    const admin = await createUser("admin");
    const source = await createProfileFixture({ owner, visibility: "private" });

    expect((await profileById(owner, source.agentId)).id).toBe(source.agentId);
    expect((await profileById(admin, source.agentId)).id).toBe(source.agentId);
    expect(await store.get(other, source.agentId)).toBeNull();
    expectListed(await store.list(owner), source.agentId, true);
    expectListed(await store.list(admin), source.agentId, true);
    expectListed(await store.list(other), source.agentId, false);
  });

  test("stores hiding per user and moves the caller between default and hidden lists", async () => {
    const owner = await createUser();
    const other = await createUser();
    const source = await createProfileFixture({ owner, visibility: "public" });

    expectListed(await store.list(owner), source.agentId, true);
    expectListed(await store.list(owner, true), source.agentId, false);
    expectListed(await store.list(other), source.agentId, true);

    await store.setHidden(owner, source.agentId, true);
    expectListed(await store.list(owner), source.agentId, false);
    expectListed(await store.list(owner, true), source.agentId, true);
    expectListed(await store.list(other), source.agentId, true);
    expectListed(await store.list(other, true), source.agentId, false);

    await store.setHidden(owner, source.agentId, false);
    expectListed(await store.list(owner), source.agentId, true);
    expectListed(await store.list(owner, true), source.agentId, false);
    const [preference] = await database
      .select()
      .from(agentPreferences)
      .where(
        and(
          eq(agentPreferences.userId, owner.id),
          eq(agentPreferences.agentId, source.agentId),
        ),
      );
    expect(preference?.hiddenAt).toBeNull();
  });

  test("takes the endpoint and ignores every field a caller must not set", async () => {
    const owner = await createUser();
    const deploymentPackage = await createPackage();
    const source = await createProfileFixture({
      owner,
      visibility: "private",
      configuration: { endpoint: "https://preserved.example.test/ag-ui" },
    });
    const oldTimestamp = new Date("2000-01-01T00:00:00.000Z");
    await database
      .update(agents)
      .set({ updatedAt: oldTimestamp })
      .where(eq(agents.id, source.agentId));
    await database
      .update(agentProfiles)
      .set({ updatedAt: oldTimestamp })
      .where(eq(agentProfiles.agentId, source.agentId));

    const result = await store.update(owner, source.agentId, {
      name: "Renamed Assistant",
      title: "Updated Title",
      roleDescription: "Updated role description.",
      visibility: "public",
      id: "forged-id",
      // The endpoint IS editable, and is the one field in this hostile payload that lands. A service
      // moves host, and the alternative is deleting the coworker and losing its conversations. It
      // reaches here already validated by the same check that guards creation.
      endpoint: "https://moved.example.test/ag-ui",
      ownerUserId: "forged-owner",
      avatarSeed: "forged-avatar",
      packageId: deploymentPackage.id,
      deletedAt: new Date(),
    } as unknown as CreateAgentInput);

    expect(result).toMatchObject({
      id: source.agentId,
      name: "Renamed Assistant",
      title: "Updated Title",
      roleDescription: "Updated role description.",
      visibility: "public",
      ownerUserId: owner.id,
      avatarSeed: source.avatarSeed,
      systemOwned: false,
      deletedAt: null,
    });
    const [canonical] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, source.agentId));
    const [profile] = await database
      .select()
      .from(agentProfiles)
      .where(eq(agentProfiles.agentId, source.agentId));
    expect(canonical).toMatchObject({
      id: source.agentId,
      name: "Renamed Assistant",
      type: "remote_ag_ui",
      configuration: { endpoint: "https://moved.example.test/ag-ui" },
      packageId: null,
    });
    expect(profile).toMatchObject({
      ownerUserId: owner.id,
      title: "Updated Title",
      roleDescription: "Updated role description.",
      avatarSeed: source.avatarSeed,
      visibility: "public",
      deletedAt: null,
    });
    expect(canonical?.updatedAt.getTime()).toBeGreaterThan(
      oldTimestamp.getTime(),
    );
    expect(profile?.updatedAt.getTime()).toBeGreaterThan(
      oldTimestamp.getTime(),
    );
  });

  test("rejects public non-owner mutation as unmanageable and inaccessible private mutation as absent", async () => {
    const owner = await createUser();
    const other = await createUser();
    const publicSource = await createProfileFixture({
      owner,
      visibility: "public",
    });
    const privateSource = await createProfileFixture({
      owner,
      visibility: "private",
    });
    const input: CreateAgentInput = {
      name: "Other Name",
      title: "Other Title",
      roleDescription: "Other role.",
      visibility: "public",
    };

    await expect(
      store.update(other, publicSource.agentId, input),
    ).rejects.toBeInstanceOf(AgentNotManageableError);
    await store.setHidden(other, publicSource.agentId, true);
    expectListed(await store.list(other), publicSource.agentId, false);
    expectListed(await store.list(other, true), publicSource.agentId, true);
    await expect(
      store.update(other, privateSource.agentId, input),
    ).rejects.toBeInstanceOf(AgentNotFoundError);
    await expect(
      store.setHidden(other, privateSource.agentId, true),
    ).rejects.toBeInstanceOf(AgentNotFoundError);
  });

  test("rejects update and soft delete for a package-backed profile", async () => {
    const owner = await createUser();
    const deploymentPackage = await createPackage();
    const source = await createProfileFixture({
      owner,
      packageId: deploymentPackage.id,
    });
    const input: CreateAgentInput = {
      name: "Protected Rename",
      title: "Protected Title",
      roleDescription: "Protected role.",
      visibility: "public",
    };

    const profile = await profileById(owner, source.agentId);
    expect(profile.systemOwned).toBe(true);
    await expect(
      store.update(owner, source.agentId, input),
    ).rejects.toBeInstanceOf(ProtectedAgentError);
    await expect(
      store.softDelete(owner, source.agentId),
    ).rejects.toBeInstanceOf(ProtectedAgentError);
  });

  test("serializes update authorization against concurrent package attachment", async () => {
    const owner = await createUser();
    const deploymentPackage = await createPackage();
    const source = await createProfileFixture({
      owner,
      name: "Original Name",
      title: "Original Title",
      roleDescription: "Original role.",
    });

    const { blocked, outcome } = await racePackageAttachment(
      source.agentId,
      deploymentPackage.id,
      (namedStore) =>
        namedStore.update(owner, source.agentId, {
          name: "Racing Rename",
          title: "Racing Title",
          roleDescription: "Racing role.",
          visibility: "public",
        }),
    );

    expect(outcome.status).toBe("rejected");
    expect(blocked).toBe(true);
    if (outcome.status === "rejected") {
      expect(outcome.reason).toBeInstanceOf(ProtectedAgentError);
    }
    const [canonical] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, source.agentId));
    const [profile] = await database
      .select()
      .from(agentProfiles)
      .where(eq(agentProfiles.agentId, source.agentId));
    expect(canonical?.name).toBe(source.name);
    expect(canonical?.packageId).toBe(deploymentPackage.id);
    expect(profile).toMatchObject({
      deletedAt: null,
      roleDescription: source.roleDescription,
      title: source.title,
      visibility: "private",
    });
  });

  test("serializes soft-delete authorization against concurrent package attachment", async () => {
    const owner = await createUser();
    const deploymentPackage = await createPackage();
    const source = await createProfileFixture({ owner });

    const { blocked, outcome } = await racePackageAttachment(
      source.agentId,
      deploymentPackage.id,
      (namedStore) => namedStore.softDelete(owner, source.agentId),
    );

    expect(outcome.status).toBe("rejected");
    expect(blocked).toBe(true);
    if (outcome.status === "rejected") {
      expect(outcome.reason).toBeInstanceOf(ProtectedAgentError);
    }
    const [canonical] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, source.agentId));
    const [profile] = await database
      .select()
      .from(agentProfiles)
      .where(eq(agentProfiles.agentId, source.agentId));
    expect(canonical?.packageId).toBe(deploymentPackage.id);
    expect(profile?.deletedAt).toBeNull();
  });

  test("allows an admin to update and soft delete a user-owned profile", async () => {
    const owner = await createUser();
    const admin = await createUser("admin");
    const source = await createProfileFixture({ owner });

    const updated = await store.update(admin, source.agentId, {
      name: "Admin Rename",
      title: "Admin Title",
      roleDescription: "Admin role update.",
      visibility: "private",
    });
    expect(updated).toMatchObject({
      name: "Admin Rename",
      ownerUserId: owner.id,
      title: "Admin Title",
    });

    await store.softDelete(admin, source.agentId);
    expect(await store.get(admin, source.agentId)).toBeNull();
  });

  test("duplicates a profile as a caller-owned private agent with copied presentation fields", async () => {
    const owner = await createUser();
    const source = await createProfileFixture({
      owner,
      visibility: "public",
      name: "Source Name",
      title: "Source Title",
      roleDescription: "Source role.",
      avatarSeed: "source-avatar",
    });
    await store.setHidden(owner, source.agentId, true);

    const duplicate = await store.duplicate(owner, source.agentId);

    expect(duplicate.id).toMatch(
      /^agent_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(duplicate).toMatchObject({
      name: source.name,
      title: source.title,
      roleDescription: source.roleDescription,
      avatarSeed: source.avatarSeed,
      visibility: "private",
      ownerUserId: owner.id,
      systemOwned: false,
      hidden: false,
      deletedAt: null,
    });
    expect(duplicate.id).not.toBe(source.agentId);
    createdAgentIds.push(duplicate.id);
    const duplicatePreferences = await database
      .select()
      .from(agentPreferences)
      .where(eq(agentPreferences.agentId, duplicate.id));
    expect(duplicatePreferences).toHaveLength(0);
  });

  test("duplicates no channel membership or Intelligence mapping from the source", async () => {
    const owner = await createUser();
    const source = await createProfileFixture({ owner, visibility: "public" });
    const channelId = id("channel");
    await database.insert(channels).values({
      id: channelId,
      name: "Source channel",
      description: "Links source agent to Intelligence.",
    });
    await database.insert(channelAgents).values({
      channelId,
      agentId: source.agentId,
    });
    await database.insert(intelligenceChannelMappings).values({
      userId: owner.id,
      channelId,
      threadId: id("thread"),
    });
    createdChannelIds.push(channelId);

    const duplicate = await store.duplicate(owner, source.agentId);
    createdAgentIds.push(duplicate.id);

    const sourceMappings = await database
      .select()
      .from(channelAgents)
      .innerJoin(
        intelligenceChannelMappings,
        eq(channelAgents.channelId, intelligenceChannelMappings.channelId),
      )
      .where(eq(channelAgents.agentId, source.agentId));
    const duplicateMappings = await database
      .select()
      .from(channelAgents)
      .innerJoin(
        intelligenceChannelMappings,
        eq(channelAgents.channelId, intelligenceChannelMappings.channelId),
      )
      .where(eq(channelAgents.agentId, duplicate.id));
    const duplicateChannelAgents = await database
      .select()
      .from(channelAgents)
      .where(eq(channelAgents.agentId, duplicate.id));
    expect(sourceMappings).not.toHaveLength(0);
    expect(duplicateChannelAgents).toHaveLength(0);
    expect(duplicateMappings).toHaveLength(0);
  });

  test("copies the source's own endpoint rather than repointing the copy at the managed Bot", async () => {
    const owner = await createUser();
    const source = await createProfileFixture({
      owner,
      configuration: { endpoint: "https://hosted.example.test/ag-ui" },
    });

    const duplicate = await store.duplicate(owner, source.agentId);
    createdAgentIds.push(duplicate.id);

    expect(duplicate.endpoint).toBe("https://hosted.example.test/ag-ui");
    expect(duplicate.endpoint).not.toBe(managedAgentAgUiUrl.toString());
  });

  test("gives a copy of an endpoint-less source the managed Bot, as its source had", async () => {
    const owner = await createUser();
    const created = await store.create(owner, {
      name: `Created ${randomUUID()}`,
      title: "Created Title",
      roleDescription: "Created role description.",
      visibility: "private",
    } as CreateAgentInput);
    createdAgentIds.push(created.id);

    const duplicate = await store.duplicate(owner, created.id);
    createdAgentIds.push(duplicate.id);

    expect(duplicate.endpoint).toBe(managedAgentAgUiUrl.toString());
  });

  test("does not carry the source's stored key onto the copy", async () => {
    const owner = await createUser();
    const source = await createProfileFixture({
      owner,
      configuration: {
        endpoint: "https://hosted.example.test/ag-ui",
        auth: { header: "Authorization", credentialId: "credential-1" },
      },
    });
    expect((await profileById(owner, source.agentId)).hasAuth).toBe(true);

    const duplicate = await store.duplicate(owner, source.agentId);
    createdAgentIds.push(duplicate.id);

    expect(duplicate.hasAuth).toBe(false);
    const [row] = await database
      .select({ configuration: agents.configuration })
      .from(agents)
      .where(eq(agents.id, duplicate.id));
    expect(authFromConfiguration(row?.configuration)).toBeNull();
  });

  test("duplicates a coworker with its own endpoint on a deployment with no managed Bot", async () => {
    const unmanagedStore = createAgentProfileStore(database, undefined);
    const owner = await createUser();
    const source = await createProfileFixture({
      owner,
      configuration: { endpoint: "https://hosted.example.test/ag-ui" },
    });

    const duplicate = await unmanagedStore.duplicate(owner, source.agentId);
    createdAgentIds.push(duplicate.id);

    expect(duplicate.endpoint).toBe("https://hosted.example.test/ag-ui");
  });

  test("refuses to duplicate an endpoint-less coworker with no managed Bot to fall back to", async () => {
    const unmanagedStore = createAgentProfileStore(database, undefined);
    const owner = await createUser();
    const source = await createProfileFixture({
      owner,
      configuration: {},
    });

    await expect(
      unmanagedStore.duplicate(owner, source.agentId),
    ).rejects.toBeInstanceOf(ManagedAgentUnavailableError);
  });

  test("soft deletes a profile from reads and lists while retaining its raw rows", async () => {
    const owner = await createUser();
    const source = await createProfileFixture({ owner, visibility: "public" });

    await store.softDelete(owner, source.agentId);

    expect(await store.get(owner, source.agentId)).toBeNull();
    expectListed(await store.list(owner), source.agentId, false);
    expectListed(await store.list(owner, true), source.agentId, false);
    const [canonical] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, source.agentId));
    const [profile] = await database
      .select()
      .from(agentProfiles)
      .where(eq(agentProfiles.agentId, source.agentId));
    expect(canonical?.id).toBe(source.agentId);
    expect(profile?.agentId).toBe(source.agentId);
    expect(profile?.deletedAt).toBeInstanceOf(Date);
    await expect(
      store.setHidden(owner, source.agentId, true),
    ).rejects.toBeInstanceOf(AgentNotFoundError);
  });

  test("rolls back canonical creation when the profile insert fails", async () => {
    const owner = await createUser();
    const name = `Rollback ${randomUUID()}`;

    await expect(
      store.create(owner, {
        name,
        title: null,
        roleDescription: "This profile insert must fail.",
        visibility: "public",
      } as unknown as CreateAgentInput),
    ).rejects.toThrow();
    const rows = await database
      .select()
      .from(agents)
      .where(eq(agents.name, name));
    expect(rows).toHaveLength(0);
  });

  /*
   * The id a caller gets is never one they chose.
   *
   * The reserved-id checks in `tenant-package.ts` rest on this: a package is the only place a Bot id
   * is written by a person, so refusing the reserved names there closes them everywhere. The day
   * this route lets a caller name their own Bot, that stops being true, and this is the test that
   * says so rather than the reader who happens to notice.
   */
  test("mints its own id rather than taking one, for a create and for a copy", async () => {
    const owner = await createUser();
    const created = await store.create(owner, {
      name: `Created ${randomUUID()}`,
      title: "Created Title",
      roleDescription: "Created role description.",
      visibility: "private",
    } as CreateAgentInput);
    createdAgentIds.push(created.id);
    const copy = await store.duplicate(owner, created.id);
    createdAgentIds.push(copy.id);

    for (const id of [created.id, copy.id]) {
      expect(id).toMatch(
        /^agent_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      );
      expect(DEPLOYMENT_ROUTES.has(id)).toBe(false);
    }
  });

  test("creates a caller-owned remote AG-UI profile with the requested visibility", async () => {
    const owner = await createUser();
    const input: CreateAgentInput = {
      name: `Created ${randomUUID()}`,
      title: "Created Title",
      roleDescription: "Created role description.",
      visibility: "public",
    };

    const created = await store.create(owner, input);
    createdAgentIds.push(created.id);

    expect(created).toMatchObject({
      name: input.name,
      title: input.title,
      roleDescription: input.roleDescription,
      avatarSeed: created.id,
      visibility: "public",
      ownerUserId: owner.id,
      systemOwned: false,
      hidden: false,
      deletedAt: null,
    });
    const [canonical] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, created.id));
    expect(canonical).toMatchObject({
      id: created.id,
      name: input.name,
      type: "remote_ag_ui",
      configuration: { endpoint: managedAgentAgUiUrl.toString() },
      packageId: null,
    });
  });
});

/*
 * Meta-Agent generated agents: the compiler-owned artifact is saved atomically as a private built-in
 * row, replayed rather than overwritten, and refused by the legacy edit/copy paths.
 */
// biome-ignore lint/suspicious/noExplicitAny: JSON columns are asserted field by field.
type FactoryBody = Record<string, any>;
describe("generated agent persistence", () => {
  const request = {
    name: "Notes",
    role: "Note summarizer",
    description: "Summarize supplied notes.",
  };
  const source = {
    kind: "request",
    field: "description",
    quote: "supplied notes",
  } as const;
  function artifact(goal = "Summarize supplied notes.") {
    const compiled = compileRecorded(request, {
      goal,
      responsibilities: [{ statement: "Summarize supplied notes.", source }],
      constraints: [],
      procedure: ["Return a concise summary."],
      requirements: [
        {
          need: "Summarize supplied text.",
          fulfillment: "model_on_input",
          source,
          proposedRefs: [],
        },
      ],
      toolArguments: [],
      inputFacts: [
        { name: "notes", required: true, missingBehavior: "Ask for notes." },
      ],
      outputExpectations: ["A summary."],
      acceptanceCriteria: ["Reflects the notes."],
      unresolvedQuestions: [],
      unsupportedRequirements: [],
    });
    if (!compiled.ok) throw new Error(JSON.stringify(compiled.issues));
    return compiled.value;
  }
  function input(
    id: string,
    options: { requestHash?: string; goal?: string; title?: unknown } = {},
  ) {
    const { spec, systemPrompt, specHash } = artifact(options.goal);
    const factory: FactoryConfiguration = {
      spec,
      verification: {
        specHash,
        construction: "PASS",
        attempts: 1,
        issues: [],
        warnings: [],
        semanticReview: {
          verdict: "PASS",
          modelRef: "fixture",
          criterionFindings: [],
        },
      },
      state: "pending_resources",
      requestHash: options.requestHash ?? "a".repeat(64),
      creationKeyHash: "b".repeat(64),
    };
    return {
      id,
      name: request.name,
      title: ("title" in options ? options.title : request.role) as string,
      roleDescription: request.description,
      systemPrompt,
      factory,
    };
  }
  const control = { timeoutMs: 5_000 };

  test("I08 a failed profile insert rolls back the canonical row", async () => {
    const owner = await createUser();
    const agentId = id("generated");
    createdAgentIds.push(agentId);
    await expect(
      store.createConstructed(owner, input(agentId, { title: null }), control),
    ).rejects.toThrow();
    const cancelled = new AbortController();
    cancelled.abort();
    await expect(
      store.createConstructed(owner, input(agentId), {
        ...control,
        signal: cancelled.signal,
      }),
    ).rejects.toThrow();
    expect(
      await database.select().from(agents).where(eq(agents.id, agentId)),
    ).toEqual([]);
    expect(
      await database
        .select()
        .from(agentProfiles)
        .where(eq(agentProfiles.agentId, agentId)),
    ).toEqual([]);
  });

  test("saves a private built-in row despite a managed endpoint; replays without overwriting", async () => {
    const owner = await createUser();
    const agentId = id("generated");
    createdAgentIds.push(agentId);
    const first = await store.createConstructed(owner, input(agentId), control);
    expect(first.created).toBe(true);
    expect(first.construction.type).toBe("built_in");
    expect(first.construction.profile).toMatchObject({
      id: agentId,
      visibility: "private",
      ownerUserId: owner.id,
      endpoint: null,
      generated: {
        state: "pending_resources",
        specHash: input(agentId).factory.verification.specHash,
      },
    });
    // Same request hash, different artifact: the committed winner is returned untouched.
    const again = await store.createConstructed(
      owner,
      input(agentId, { goal: "A different goal." }),
      control,
    );
    expect(again.created).toBe(false);
    expect(again.construction.configuration).toEqual(
      first.construction.configuration,
    );
    await expect(
      store.createConstructed(
        owner,
        input(agentId, { requestHash: "c".repeat(64) }),
        control,
      ),
    ).rejects.toBeInstanceOf(ConstructionConflictError);
    // Another actor can never adopt the row.
    const other = await createUser();
    await expect(
      store.createConstructed(other, input(agentId), control),
    ).rejects.toBeInstanceOf(ConstructionConflictError);
    expect(
      await database.select().from(agents).where(eq(agents.id, agentId)),
    ).toHaveLength(1);
    await store.softDelete(owner, agentId);
    await expect(
      store.createConstructed(owner, input(agentId), control),
    ).rejects.toBeInstanceOf(ConstructionDeletedError);
    expect(
      (await store.readConstruction(owner, agentId, { includeDeleted: true }))
        ?.profile.deletedAt,
    ).not.toBeNull();
    expect(await store.readConstruction(owner, agentId)).toBeNull();
  });

  test("reads the artifact for the owner or an administrator only, and never for legacy rows", async () => {
    const owner = await createUser();
    const other = await createUser();
    const administrator = await createUser("admin");
    const agentId = id("generated");
    createdAgentIds.push(agentId);
    await store.createConstructed(owner, input(agentId), control);
    expect((await store.readConstruction(owner, agentId))?.type).toBe(
      "built_in",
    );
    expect(await store.readConstruction(administrator, agentId)).not.toBeNull();
    expect(await store.readConstruction(other, agentId)).toBeNull();
    const legacy = await createProfileFixture({ owner });
    expect(await store.readConstruction(owner, legacy.agentId)).toBeNull();
    // The roster carries a compact summary and no spec; legacy profiles carry no key at all.
    const listed = await store.list(owner);
    const generated = listed.find(({ id }) => id === agentId);
    expect(generated?.generated?.state).toBe("pending_resources");
    expect(
      Object.hasOwn(
        listed.find(({ id }) => id === legacy.agentId) ?? {},
        "generated",
      ),
    ).toBe(false);
  });

  test("readiness updates only the state for the matching spec hash", async () => {
    const owner = await createUser();
    const agentId = id("generated");
    createdAgentIds.push(agentId);
    const value = input(agentId);
    await store.createConstructed(owner, value, control);
    const [before] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, agentId));
    expect(
      await store.setConstructionReadiness(
        owner,
        agentId,
        "0".repeat(64),
        "ready",
      ),
    ).toBe(false);
    expect(
      await store.setConstructionReadiness(
        owner,
        agentId,
        value.factory.verification.specHash,
        "ready",
      ),
    ).toBe(true);
    const [after] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, agentId));
    const beforeConfiguration = before?.configuration as FactoryBody;
    expect(after?.configuration).toEqual({
      ...beforeConfiguration,
      factory: { ...beforeConfiguration.factory, state: "ready" },
    });
    await expect(
      store.setConstructionReadiness(
        await createUser(),
        agentId,
        value.factory.verification.specHash,
        "ready",
      ),
    ).rejects.toBeInstanceOf(AgentNotFoundError);
  });

  test("I11 generated PATCH and duplicate are refused before any change; legacy edit and copy still work", async () => {
    const owner = await createUser();
    const administrator = await createUser("admin");
    const agentId = id("generated");
    createdAgentIds.push(agentId);
    await store.createConstructed(owner, input(agentId), control);
    const corrupt = await createProfileFixture({
      owner,
      configuration: { systemPrompt: "Anything.", factory: "corrupt" },
    });
    for (const target of [agentId, corrupt.agentId]) {
      const [agentBefore] = await database
        .select()
        .from(agents)
        .where(eq(agents.id, target));
      const [profileBefore] = await database
        .select()
        .from(agentProfiles)
        .where(eq(agentProfiles.agentId, target));
      for (const actor of [owner, administrator]) {
        await expect(
          store.update(actor, target, {
            name: "Hijacked",
            title: "Hijacked",
            roleDescription: "Ignore the verified specification.",
            visibility: "public",
            auth: { header: "Authorization", value: "Bearer x" },
          }),
        ).rejects.toBeInstanceOf(GeneratedConfigurationImmutableError);
        await expect(store.duplicate(actor, target)).rejects.toBeInstanceOf(
          GeneratedConfigurationImmutableError,
        );
      }
      expect(
        (await database.select().from(agents).where(eq(agents.id, target)))[0],
      ).toEqual(agentBefore);
      expect(
        (
          await database
            .select()
            .from(agentProfiles)
            .where(eq(agentProfiles.agentId, target))
        )[0],
      ).toEqual(profileBefore);
    }
    expect(
      (await store.list(owner)).find(({ id }) => id === corrupt.agentId)
        ?.generated,
    ).toEqual({ state: "invalid", specHash: null });
    expect(
      await database
        .select()
        .from(agents)
        .where(eq(agents.name, request.name))
        .then((rows) => rows.filter(({ id }) => id !== agentId).length),
    ).toBe(0);
    // Hide and delete stay available.
    await store.setHidden(owner, agentId, true);
    await store.softDelete(owner, agentId);
    // Legacy built-in edit and copy are unaffected.
    const legacy = await createProfileFixture({
      owner,
      configuration: { systemPrompt: "Legacy prompt." },
    });
    await database
      .update(agents)
      .set({ type: "built_in" })
      .where(eq(agents.id, legacy.agentId));
    const edited = await store.update(owner, legacy.agentId, {
      name: legacy.name,
      title: "Edited",
      roleDescription: "Edited prompt.",
      visibility: "private",
    });
    expect(edited.title).toBe("Edited");
    const copy = await store.duplicate(owner, legacy.agentId);
    createdAgentIds.push(copy.id);
    const [copied] = await database
      .select()
      .from(agents)
      .where(eq(agents.id, copy.id));
    expect(copied?.configuration).toEqual({ systemPrompt: "Edited prompt." });
  });
});
