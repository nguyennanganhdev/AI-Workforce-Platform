/**
 * Harness cho test WRITE của Security MCP: mock có điều khiển, write guard với hai issuer, ký grant
 * theo đồng hồ mock (cùng đồng hồ với wrapper), và ký token thô để dựng grant sai có chủ ý.
 */
import { createHash, createHmac } from "node:crypto";
import { createLocalJWKSet, exportJWK, generateKeyPair } from "jose";
import type {
  Actor,
  RequestIdentity,
} from "../../../src/security-tools/common/context";
import {
  type ActionBinding,
  createWriteGuard,
  GRANT_AUDIENCE,
  GRANT_TYP,
  payloadHash,
  type WriteAction,
} from "../../../src/security-tools/common/execution-grant";
import {
  createMockClock,
  createMockEnvironment,
} from "../../../src/security-tools/providers/mock-control";
import {
  loadFixtureScope,
  MockSecurityProvider,
} from "../../../src/security-tools/providers/mock-provider";
import {
  createWriteControl,
  createWriteHandlers,
  MockOperationLedger,
} from "../../../src/security-tools/providers/mock-write";
import type { SecurityProvider } from "../../../src/security-tools/providers/provider";
import {
  callTool,
  type SecurityToolsOptions,
} from "../../../src/security-tools/tools";

// biome-ignore lint/suspicious/noExplicitAny: envelope JSON của contract, test đọc field lồng nhau
export type Row = Record<string, any>;

export const ISSUER = "https://platform.test";
export const OTHER_ISSUER = "https://platform-b.test";
export const EXECUTOR = "executor";
export const ACTOR: Actor = { actor_id: "usr_sup_day", actor_type: "HUMAN" };

/** Ticket của từng incident trong fixture: WRITE trên incident phải đi bằng phiên của đúng ticket đó. */
export const TICKET = {
  inc_01: "tkt_1001",
  inc_02: "tkt_1002",
  inc_03: "tkt_1003",
  inc_04: "tkt_1004",
} as const;

export type Session = {
  tenant_id: string;
  property_id: string;
  ticket_id: string;
  task_id: string;
};
export const session = (
  ticket_id: string = TICKET.inc_01,
  extra: Partial<Session> = {},
): Session => ({
  tenant_id: "tenant_demo",
  property_id: "property_demo",
  ticket_id,
  task_id: "task_1",
  ...extra,
});

const main = await generateKeyPair("ES256", { extractable: true });
const other = await generateKeyPair("ES256", { extractable: true });
export const KEYS = { main, other } as const;
const jwk = async (key: CryptoKey, kid: string) => ({
  ...(await exportJWK(key)),
  kid,
  alg: "ES256",
});

export const writeGuard = createWriteGuard({
  issuers: {
    [ISSUER]: createLocalJWKSet({ keys: [await jwk(main.publicKey, "g1")] }),
    [OTHER_ISSUER]: createLocalJWKSet({
      keys: [await jwk(other.publicKey, "g2")],
    }),
  },
});

const b64 = (data: string | Uint8Array) =>
  Buffer.from(data).toString("base64url");

/** Ký compact JWS ES256 từ header/payload thô; không qua jose nên dựng được header/claims sai tùy ý. */
export async function signRaw(
  header: Row,
  payload: Row,
  key: CryptoKey = main.privateKey,
): Promise<string> {
  const input = `${b64(JSON.stringify(header))}.${b64(JSON.stringify(payload))}`;
  const signature = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    key,
    new TextEncoder().encode(input),
  );
  return `${input}.${b64(new Uint8Array(signature))}`;
}

/** HS256 dùng public key làm secret: kiểu tấn công nhầm thuật toán. */
export async function signHs256(header: Row, payload: Row): Promise<string> {
  const secret = Buffer.from(JSON.stringify(await exportJWK(main.publicKey)));
  const input = `${b64(JSON.stringify(header))}.${b64(JSON.stringify(payload))}`;
  return `${input}.${createHmac("sha256", secret).update(input).digest("base64url")}`;
}

export const sha256 = (text: string) =>
  createHash("sha256").update(text, "utf8").digest("hex");

export type GrantSpec = {
  action: WriteAction;
  args: Row;
  key: string;
  session?: Session;
  actor?: Actor;
  proposal?: string;
};

export function bindingOf(spec: GrantSpec): ActionBinding {
  return {
    contract_version: "0.3",
    proposal_id: spec.proposal ?? `prop_${spec.key}`,
    ...(spec.session ?? session()),
    actor: spec.actor ?? ACTOR,
    action: spec.action,
    idempotency_key: spec.key,
    arguments: spec.args,
  };
}

export function createHarness(options: { useOwnLedger?: boolean } = {}) {
  const env = createMockEnvironment({ cursorSecret: "test-secret" });
  // Ledger riêng chỉ khi test cần đọc/archive operation (createMockEnvironment không lộ ledger).
  const own = options.useOwnLedger ? ownProvider() : null;
  const provider: SecurityProvider = own?.provider ?? env.provider;
  const clock = own?.clock ?? env.clock;

  /** Claims hợp lệ theo giờ mock; `patch` ghi đè claim, `drop` bỏ claim. */
  function claimsFor(
    spec: GrantSpec,
    patch: Row = {},
    drop: string[] = [],
  ): Row {
    const binding = bindingOf(spec);
    const { arguments: _args, ...base } = binding;
    const iat = Math.floor(clock.now().getTime() / 1000);
    const claims: Row = {
      ...base,
      iss: ISSUER,
      aud: GRANT_AUDIENCE,
      sub: EXECUTOR,
      jti: `jti_${spec.key}_${iat}`,
      iat,
      nbf: iat,
      exp: iat + 120,
      payload_hash: payloadHash(binding),
      ...patch,
    };
    for (const name of drop) delete claims[name];
    return claims;
  }

  const header = (patch: Row = {}) => ({
    alg: "ES256",
    typ: GRANT_TYP,
    kid: "g1",
    ...patch,
  });

  async function grant(
    spec: GrantSpec,
    patch: Row = {},
    headerPatch: Row = {},
    key?: CryptoKey,
  ) {
    return signRaw(header(headerPatch), claimsFor(spec, patch), key);
  }

  function identity(
    s: Session,
    grantToken: string | null,
    key: string | null,
    principal = EXECUTOR,
  ): RequestIdentity {
    return {
      caller: {
        principal_id: principal,
        ...s,
        modes: new Set(["READ", "WRITE"]),
      },
      correlation_id: "corr_p5",
      write_headers: { execution_grant: grantToken, idempotency_key: key },
    };
  }

  const opts = (): SecurityToolsOptions => ({
    provider,
    writeGuard,
    now: clock.now,
    onOutputRejected: () => {},
  });

  /** WRITE với grant hợp lệ cho đúng spec, hoặc token/header tùy chỉnh. */
  async function write(
    spec: GrantSpec,
    over: {
      token?: string | null;
      headerKey?: string | null;
      sentArgs?: Row;
      principal?: string;
    } = {},
  ) {
    const token = over.token === undefined ? await grant(spec) : over.token;
    const key = over.headerKey === undefined ? spec.key : over.headerKey;
    const result = await callTool(
      spec.action,
      over.sentArgs ?? spec.args,
      identity(spec.session ?? session(), token, key, over.principal),
      opts(),
    );
    return result.structuredContent as Row;
  }

  async function read(name: string, args: Row, s: Session = session()) {
    const result = await callTool(
      name,
      args,
      {
        ...identity(s, null, null),
        caller: { ...identity(s, null, null).caller, modes: new Set(["READ"]) },
      },
      opts(),
    );
    return result.structuredContent as Row;
  }

  return {
    env,
    provider,
    clock,
    get ledger(): MockOperationLedger | null {
      return own?.ledger ?? null;
    },
    get control() {
      return own?.control ?? env.control;
    },
    claimsFor,
    header,
    grant,
    identity,
    write,
    read,
    reset() {
      env.reset();
      own?.reset();
    },
  };
}

/** Provider mock dựng tay để giữ được ledger (archive, đọc operation như `getOperation` của Core). */
function ownProvider() {
  const clock = createMockClock();
  let control = createWriteControl();
  let ledger = new MockOperationLedger();
  let current = build();
  function build() {
    return new MockSecurityProvider({
      scopes: [loadFixtureScope()],
      now: clock.now,
      cursorSecret: "test-secret",
      writeHandlers: createWriteHandlers({ control, ledger }),
    });
  }
  const box = {
    clock,
    get control() {
      return control;
    },
    get ledger() {
      return ledger;
    },
    provider: {
      name: "mock",
      read: (...a) => current.read(...a),
      write: (...a) => current.write(...a),
    } as SecurityProvider,
    reset() {
      control = createWriteControl();
      ledger = new MockOperationLedger();
      clock.reset();
      current = build();
    },
  };
  return box;
}

export function expectFailure(env: Row, code: string | string[]) {
  const codes = Array.isArray(code) ? code : [code];
  if (env.success !== false || !codes.includes(env.error?.code)) {
    throw new Error(
      `Cần failure ${codes.join("|")}, nhận ${JSON.stringify(env.error ?? env.data)}`,
    );
  }
  return env.error as Row;
}
