import { ne, sql } from "drizzle-orm";
import type { Database } from "../db/client";
import { users } from "../db/schema";
import { DEV_ACTOR } from "./dev-actor";
import type { AuthenticatedActor } from "./guards";
import { rolesForUser, setRole } from "./roles";

/** Reconcile only an employee verified by the pinned authority; retain existing local history IDs. */
export function organizationUserStore(database: Database) {
  return async (user: AuthenticatedActor) => {
    const [known] = await database
      .select({ id: users.id, status: users.status })
      .from(users)
      .where(sql`lower(${users.email})=${user.email.toLowerCase()}`);
    if (known && (known.status === "suspended" || known.status === "deleted")) {
      throw new Error(
        "Organization sign-in cannot restore a disabled local account.",
      );
    }
    const [local] = await database
      .insert(users)
      .values({
        id: known?.id ?? user.id,
        email: user.email,
        name: user.name,
        image: user.image,
      })
      .onConflictDoUpdate({
        target: users.id,
        setWhere: ne(users.id, DEV_ACTOR.id),
        set: {
          email: user.email,
          name: user.name,
          image: user.image,
          updatedAt: new Date(),
        },
      })
      .returning({ id: users.id });
    if (!local || local.id === DEV_ACTOR.id)
      throw new Error(
        "Organization sign-in cannot use the standalone account.",
      );
    if (user.role === "management" || user.role === "staff") {
      const grants = await rolesForUser(database, local.id);
      if (!grants.includes(user.role)) {
        throw new Error(
          "Organization role requires an existing local scoped grant.",
        );
      }
    } else {
      await setRole(database, local.id, user.role);
    }
    return { ...user, id: local.id };
  };
}
