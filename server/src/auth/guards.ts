import type { Context, MiddlewareHandler } from "hono";
import type { Database } from "../db/client";
import { rolesForUser, strongestRole } from "./roles";
import type { OpenBotRole } from "./roles";

export type AuthenticatedActor = {
  id: string;
  email: string;
  name?: string | null;
  image?: string | null;
  role: OpenBotRole;
};

export type AuthService = {
  handler: (request: Request) => Response | Promise<Response>;
  api: {
    getSession: (input: {
      headers: Headers;
      query?: { disableCookieCache: boolean };
    }) => Promise<{
      user: {
        id: string;
        email: string;
        name?: string | null;
        image?: string | null;
        /** Set only by a server-verified organization authority. */
        role?: OpenBotRole;
      };
    } | null>;
  };
};

export type RoleRepository = {
  rolesForUser: (userId: string) => Promise<OpenBotRole[]>;
};

export type AppVariables = {
  actor: AuthenticatedActor;
};

export function createRoleRepository(database: Database): RoleRepository {
  return {
    rolesForUser: (userId) => rolesForUser(database, userId),
  };
}

export function createRequireUser(
  auth: AuthService,
  roleRepository: RoleRepository,
): MiddlewareHandler<{ Variables: AppVariables }> {
  return async (context, next) => {
    const session = await auth.api.getSession({
      headers: context.req.raw.headers,
      query: { disableCookieCache: true },
    });

    if (!session) {
      return context.json({ error: "Authentication required." }, 401);
    }

    // Canonical DB grants also enforce suspended accounts. Provider claims cannot bypass revocation.
    const roles = await roleRepository.rolesForUser(session.user.id);
    const role = strongestRole(roles);

    if (!role) {
      return context.json({ error: "Authorization required." }, 403);
    }

    context.set("actor", {
      id: session.user.id,
      email: session.user.email,
      name: session.user.name,
      image: session.user.image,
      role,
    });
    await next();
  };
}

export function requireAdmin(context: Context<{ Variables: AppVariables }>) {
  if (context.var.actor.role !== "admin") {
    return context.json({ error: "Administrator access required." }, 403);
  }

  return undefined;
}
