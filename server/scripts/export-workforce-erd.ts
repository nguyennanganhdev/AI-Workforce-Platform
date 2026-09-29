/** Deterministic physical ERDs and data dictionary from the actual Drizzle model. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { getTableName, is, SQL } from "drizzle-orm";
import { getTableConfig, PgDialect, PgTable } from "drizzle-orm/pg-core";
import * as authorization from "../src/db/schema/authorization";
import * as components from "../src/db/schema/components";
import * as computer from "../src/db/schema/computer";
import * as core from "../src/db/schema/core";
import * as coworker from "../src/db/schema/coworker";
import * as assets from "../src/db/schema/domains/vinhomes/assets";
import * as attachments from "../src/db/schema/domains/vinhomes/attachments";
import * as billing from "../src/db/schema/domains/vinhomes/billing";
import * as booking from "../src/db/schema/domains/vinhomes/booking";
import * as communication from "../src/db/schema/domains/vinhomes/communication";
import * as content from "../src/db/schema/domains/vinhomes/content";
import * as delivery from "../src/db/schema/domains/vinhomes/delivery";
import * as dispatch from "../src/db/schema/domains/vinhomes/dispatch";
import * as evidence from "../src/db/schema/domains/vinhomes/evidence";
import * as files from "../src/db/schema/domains/vinhomes/files";
import * as intake from "../src/db/schema/domains/vinhomes/intake";
import * as operations from "../src/db/schema/domains/vinhomes/operations";
import * as property from "../src/db/schema/domains/vinhomes/property";
import * as providerEvents from "../src/db/schema/domains/vinhomes/provider-events";
import * as residentUpdates from "../src/db/schema/domains/vinhomes/resident-updates";
import * as services from "../src/db/schema/domains/vinhomes/services";
import * as sla from "../src/db/schema/domains/vinhomes/sla";
import * as workforce from "../src/db/schema/domains/vinhomes/workforce";
import * as agents from "../src/db/schema/platform/agents";
import * as audit from "../src/db/schema/platform/audit";
import * as capabilities from "../src/db/schema/platform/capabilities";
import * as collaboration from "../src/db/schema/platform/collaboration";
import * as conversations from "../src/db/schema/platform/conversations";
import * as deployments from "../src/db/schema/platform/deployments";
import * as domains from "../src/db/schema/platform/domains";
import * as evaluation from "../src/db/schema/platform/evaluation";
import * as eventDelivery from "../src/db/schema/platform/event-delivery";
import * as identity from "../src/db/schema/platform/identity";
import * as memory from "../src/db/schema/platform/memory";
import * as runtime from "../src/db/schema/platform/runtime";
import * as plugins from "../src/db/schema/plugins";
import * as voice from "../src/db/schema/voice";
import * as work from "../src/db/schema/work";
import purposes from "./table-purposes.json";

const groups: Record<string, Record<string, unknown>> = {
  authorization: authorization,
  "foundation-core": core,
  "foundation-computer": computer,
  "foundation-coworker": coworker,
  "foundation-components": components,
  "foundation-plugins": plugins,
  "foundation-work": work,
  "foundation-voice": voice,
  "platform-identity": identity,
  "platform-domains": domains,
  "platform-agents": agents,
  "platform-capabilities": capabilities,
  "platform-evaluation": evaluation,
  "platform-deployments": deployments,
  "platform-runtime": runtime,
  "platform-memory": memory,
  "platform-audit": audit,
  "vinhomes-property": property,
  "vinhomes-intake": intake,
  "vinhomes-operations": operations,
  "vinhomes-files": files,
  "vinhomes-evidence": evidence,
  "vinhomes-attachments": attachments,
  "vinhomes-communication": communication,
  "vinhomes-services": services,
  "vinhomes-booking": booking,
  "vinhomes-billing": billing,
  "vinhomes-content": content,
  "vinhomes-delivery": delivery,
  "platform-conversations": conversations,
  "platform-collaboration": collaboration,
  "platform-event-delivery": eventDelivery,
  "vinhomes-workforce": workforce,
  "vinhomes-assets": assets,
  "vinhomes-dispatch": dispatch,
  "vinhomes-resident-updates": residentUpdates,
  "vinhomes-provider-events": providerEvents,
  "vinhomes-sla": sla,
};
const purposeByName: Record<string, string> = purposes;
const catalog = [
  "# Danh mục nhiệm vụ từng bảng",
  "",
  "Sinh từ schema và `server/scripts/table-purposes.json`. Nhấn tên bảng để xem mọi trường, kiểu dữ liệu, khóa và ràng buộc.",
  "",
  "[Luồng toàn hệ thống](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md) · [ERD quan hệ toàn dự án](PROJECT_RELATIONSHIPS.md)",
  "",
];
const relationships = [
  "# ERD quan hệ toàn dự án",
  "",
  "Tất cả bảng và FK thực tế; chia sơ đồ chi tiết theo module tại [catalog](README.md). Cạnh này là FK, không phải luồng gọi API. Tham chiếu mềm domain/runtime được giải thích tại [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).",
  "",
];
const seen = new Set<string>();
const dialect = new PgDialect();
const quote = (value: unknown) => {
  if (value === undefined) return "—";
  if (is(value, SQL)) return dialect.sqlToQuery(value).sql;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};
const code = (value: unknown) =>
  `\`${quote(value).replaceAll("|", "\\|").replaceAll("`", "'")}\``;
const output = new URL("../../docs/erd/physical/", import.meta.url);
const check = process.argv.includes("--check");
let stale = false;
async function emit(name: string, lines: string[]) {
  const text = `${lines.join("\n").trimEnd()}\n`;
  if (check) {
    const actual = await readFile(new URL(name, output), "utf8").catch(
      () => "",
    );
    if (actual !== text) {
      console.error(`ERD out of date: ${name}`);
      stale = true;
    }
  } else {
    await mkdir(output, { recursive: true });
    await writeFile(new URL(name, output), text);
  }
}

const index = [
  "# Physical database catalog",
  "",
  "Generated from Drizzle; update with `bun run db:erd`. Do not edit generated pages.",
  "",
  "Logical intent and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md).",
  "",
  "| Module | Tables |",
  "|---|---:|",
];
let count = 0;
for (const [group, exports] of Object.entries(groups)) {
  const tables = Object.values(exports)
    .filter(
      (v): v is PgTable =>
        is(v, PgTable) &&
        !(group === "platform-identity" && getTableName(v) === "users"),
    )
    .sort((a, b) => getTableName(a).localeCompare(getTableName(b)));
  count += tables.length;
  catalog.push(
    `## ${group}`,
    "",
    "| Bảng | Nhiệm vụ | Liên kết tới |",
    "|---|---|---|",
  );
  relationships.push(
    `## ${group}`,
    "",
    `Fields and constraints: [${group}](${group}.md).`,
    "",
    "```mermaid",
    "erDiagram",
  );
  index.push(`| [${group}](${group}.md) | ${tables.length} |`);
  const lines = [
    `# ${group}`,
    "",
    "Generated from Drizzle. External entities in the diagram are foreign-key targets owned by another module.",
    "",
    "```mermaid",
    "erDiagram",
  ];
  for (const table of tables) {
    const config = getTableConfig(table);
    if (seen.has(config.name))
      throw new Error(`Duplicate table ${config.name}`);
    seen.add(config.name);
    if (!purposeByName[config.name])
      throw new Error(`Missing purpose: ${config.name}`);
    catalog.push(
      `| [${config.name}](${group}.md#${config.name}) | ${purposeByName[config.name]} | ${[...new Set(config.foreignKeys.map((fk) => getTableName(fk.reference().foreignTable)))].map((name) => `\`${name}\``).join(", ") || "—"} |`,
    );
    relationships.push(`  ${config.name}`);
    lines.push(`  ${config.name} {`);
    for (const col of config.columns) {
      const pk =
        col.primary ||
        config.primaryKeys.some((k) =>
          k.columns.some((c) => c.name === col.name),
        );
      const fk = config.foreignKeys.some((k) =>
        k.reference().columns.some((c) => c.name === col.name),
      );
      const markers = [pk ? "PK" : "", fk ? "FK" : ""]
        .filter(Boolean)
        .join(", ");
      lines.push(
        `    ${col.getSQLType().replaceAll(/[^a-zA-Z0-9_]/g, "_")} ${col.name}${markers ? ` ${markers}` : ""}`,
      );
    }
    lines.push("  }");
    for (const key of config.foreignKeys) {
      const ref = key.reference();
      const nullable = ref.columns.some((c) => !c.notNull);
      const columns = ref.columns.map((c) => c.name);
      const unique =
        (columns.length === 1 &&
          config.columns.some(
            (c) => c.name === columns[0] && (c.primary || c.isUnique),
          )) ||
        config.uniqueConstraints.some(
          (u) =>
            u.columns.length === columns.length &&
            u.columns.every((c) => columns.includes(c.name)),
        ) ||
        config.primaryKeys.some(
          (u) =>
            u.columns.length === columns.length &&
            u.columns.every((c) => columns.includes(c.name)),
        );
      const edge = `  ${getTableName(ref.foreignTable)} ${nullable ? "|o" : "||"}--${unique ? "o|" : "o{"} ${config.name} : "${columns.filter((c) => c !== "tenant_id" && c !== "project_id").join(" + ") || "ownership"}"`;
      lines.push(edge);
      relationships.push(edge);
    }
  }
  lines.push("```", "");
  for (const table of tables) {
    const c = getTableConfig(table);
    lines.push(
      `## ${c.name}`,
      "",
      purposeByName[c.name] ?? "",
      "",
      `Tenant RLS: **${c.enableRLS ? "enabled + forced by integrity migrations 0047/0049/0052" : "global identity or deployment infrastructure; application/operator authorization required"}**.`,
      "",
      "| Column | PostgreSQL type | Required | Default | Declared values |",
      "|---|---|---|---|---|",
    );
    for (const col of c.columns)
      lines.push(
        `| ${code(col.name)} | ${code(col.getSQLType())} | ${col.notNull ? "yes" : "no"} | ${code(col.default)} | ${col.enumValues?.length ? col.enumValues.map(code).join(", ") : "—"} |`,
      );
    const primary = [
      ...c.columns.filter((col) => col.primary).map((col) => col.name),
      ...c.primaryKeys.flatMap((k) => k.columns.map((col) => col.name)),
    ];
    lines.push("", `Primary key: ${primary.map(code).join(", ")}.`, "");
    if (c.uniqueConstraints.length || c.columns.some((col) => col.isUnique)) {
      lines.push("Unique keys:", "");
      for (const col of c.columns.filter((col) => col.isUnique))
        lines.push(`- ${code(col.uniqueName)}: (${code(col.name)}).`);
      for (const key of c.uniqueConstraints)
        lines.push(
          `- ${code(key.name)}: (${key.columns.map((col) => code(col.name)).join(", ")}).`,
        );
      lines.push("");
    }
    if (c.foreignKeys.length) {
      lines.push("Foreign keys:", "");
      for (const key of c.foreignKeys) {
        const ref = key.reference();
        lines.push(
          `- (${ref.columns.map((col) => code(col.name)).join(", ")}) → ${code(getTableName(ref.foreignTable))} (${ref.foreignColumns.map((col) => code(col.name)).join(", ")}); ON DELETE ${code(key.onDelete ?? "no action")}.`,
        );
      }
      lines.push("");
    }
    if (c.indexes.length) {
      lines.push("Indexes:", "");
      for (const { config: ix } of c.indexes)
        lines.push(
          `- ${code(ix.name)}${ix.unique ? " UNIQUE" : ""}: (${ix.columns.map((col) => code("name" in col ? col.name : col)).join(", ")})${ix.where ? ` WHERE ${code(ix.where)}` : ""}.`,
        );
      lines.push("");
    }
    if (c.checks.length) {
      lines.push("Checks:", "");
      for (const ck of c.checks)
        lines.push(`- ${code(ck.name)}: ${code(ck.value)}.`);
      lines.push("");
    }
    lines.push(
      "Cross-row rules and application responsibilities: [database design](../01_DATABASE_ERD_IMPLEMENTATION_COMPLETE.md) and [system flow](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).",
      "",
    );
  }
  await emit(`${group}.md`, lines);
  catalog.push("");
  relationships.push("```", "");
}
index.push(
  "",
  `Total: **${count} tables** in one product developed from OpenBot, including Vinhomes.`,
  "",
  "[Nhiệm vụ từng bảng](TABLE_CATALOG.md) · [ERD toàn dự án](PROJECT_RELATIONSHIPS.md) · [Luồng nghiệp vụ](../02_BUSINESS_ANALYSIS_IMPLEMENTATION.md)",
);
const unused = Object.keys(purposeByName).filter((name) => !seen.has(name));
if (unused.length)
  throw new Error(`Unknown table purposes: ${unused.join(", ")}`);
await emit("TABLE_CATALOG.md", catalog);
await emit("PROJECT_RELATIONSHIPS.md", relationships);
await emit("README.md", index);
if (stale) process.exitCode = 1;
else
  console.info(
    `${check ? "Verified" : "Generated"} physical ERD: ${count} tables, ${Object.keys(groups).length} modules.`,
  );
