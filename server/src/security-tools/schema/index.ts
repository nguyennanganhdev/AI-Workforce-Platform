/**
 * Nạp ba file JSON Schema contract v0.3 (nguồn cấu trúc public duy nhất, spec §10) vào một validator
 * Draft 2020-12, và bundle từng input/output thành schema độc lập cho `tools/list`.
 *
 * Ref dùng dạng `<file>#/$defs/<Tên>`, ví dụ `common.schema.json#/$defs/Dispatch`,
 * `security_mcp.schema.json#/$defs/DispatchGuardOutput` — cùng dạng với DISPATCH_SCHEMAS của P4.
 */
import { readFileSync } from "node:fs";
import Ajv2020, {
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020";
import addFormats from "ajv-formats";
import type { ToolMode } from "../common/errors";

export const SCHEMA_FILES = [
  "common.schema.json",
  "security_mcp.schema.json",
  "security_skill.schema.json",
] as const;
export type SchemaFile = (typeof SCHEMA_FILES)[number];

type JsonObject = { [key: string]: unknown };

const documents: Record<SchemaFile, JsonObject> = Object.fromEntries(
  SCHEMA_FILES.map((file) => [
    file,
    JSON.parse(readFileSync(new URL(`./${file}`, import.meta.url), "utf8")),
  ]),
) as Record<SchemaFile, JsonObject>;

// Không coerce, không chèn default, không bỏ field lạ (từ điển schema, "JSON Schema và cách dùng").
const ajv = new Ajv2020({
  strict: true,
  // Contract dùng `anyOf: [{ required: [...] }]` cho ràng buộc có điều kiện; property được khai báo
  // ở schema cha nên strictRequired của Ajv báo sai, dù hợp lệ theo Draft 2020-12.
  strictRequired: false,
  strictTypes: false,
  strictTuples: false,
  allErrors: true,
  coerceTypes: false,
  useDefaults: false,
  removeAdditional: false,
});
addFormats(ajv, ["date-time"]);
// Danh mục tra cứu, không phải keyword validation.
ajv.addKeyword("x-tools");
ajv.addKeyword("x-skills");
for (const file of SCHEMA_FILES) ajv.addSchema(documents[file], file);

const validators = new Map<string, ValidateFunction>();

/** Validator cho một ref `<file>#/$defs/<Tên>`. Ref sai là lỗi lập trình, throw ngay. */
export function validatorFor(ref: string): ValidateFunction {
  const cached = validators.get(ref);
  if (cached) return cached;
  parseRef(ref);
  const validate = ajv.getSchema(ref);
  if (!validate) throw new Error(`Không resolve được schema ${ref}`);
  validators.set(ref, validate);
  return validate;
}

export type ValidationResult = { ok: true } | { ok: false; issues: string[] };

export function validate(ref: string, value: unknown): ValidationResult {
  const fn = validatorFor(ref);
  return fn(value)
    ? { ok: true }
    : { ok: false, issues: describeErrors(fn.errors ?? []) };
}

/**
 * Mô tả lỗi theo đường dẫn và keyword, không chép giá trị vào message (giá trị có thể là dữ liệu
 * caller/provider không tin cậy). oneOf/anyOf sinh rất nhiều lỗi con nên chỉ giữ 10 dòng đầu.
 */
export function describeErrors(errors: readonly ErrorObject[]): string[] {
  const lines = new Set<string>();
  for (const error of errors) {
    const path = error.instancePath === "" ? "(root)" : error.instancePath;
    if (error.keyword === "additionalProperties") {
      lines.add(
        `${path}: field lạ "${String(error.params.additionalProperty)}"`,
      );
    } else if (error.keyword === "required") {
      lines.add(`${path}: thiếu "${String(error.params.missingProperty)}"`);
    } else {
      lines.add(`${path}: ${error.message ?? error.keyword}`);
    }
  }
  return [...lines].slice(0, 10);
}

// ---------------------------------------------------------------------------------------------
// Danh mục tool từ `x-tools` của security_mcp.schema.json
// ---------------------------------------------------------------------------------------------

export type ToolContract = {
  name: string;
  mode: ToolMode;
  inputSchema: string;
  outputSchema: string;
};

type XTool = {
  mode: ToolMode;
  inputSchema: { $ref: string };
  outputSchema: { $ref: string };
};

/** 22 tool theo contract, đúng thứ tự trong schema. */
export const TOOL_CONTRACTS: readonly ToolContract[] = Object.entries(
  documents["security_mcp.schema.json"]["x-tools"] as Record<string, XTool>,
).map(([name, tool]) => ({
  name,
  mode: tool.mode,
  inputSchema: absoluteRef(tool.inputSchema.$ref, "security_mcp.schema.json"),
  outputSchema: absoluteRef(tool.outputSchema.$ref, "security_mcp.schema.json"),
}));

// ---------------------------------------------------------------------------------------------
// Bundle cho tools/list
// ---------------------------------------------------------------------------------------------

/**
 * Schema độc lập cho một ref: chính def đó ở root, mọi def được tham chiếu bắc cầu chép vào
 * `$defs` cục bộ, mọi `$ref` viết lại thành `#/$defs/...`. Không còn ref tới file local.
 */
export function bundleSchema(ref: string): JsonObject {
  const root = parseRef(ref);
  const names = new Map<string, string>(); // "<file>#<def>" -> tên trong $defs đã bundle
  const defs: JsonObject = {};
  const queue: { file: SchemaFile; def: string }[] = [];

  const localName = (file: SchemaFile, def: string) => {
    const key = `${file}#${def}`;
    let name = names.get(key);
    if (name === undefined) {
      const taken = new Set(names.values());
      name = taken.has(def) ? `${file.split(".")[0]}__${def}` : def;
      names.set(key, name);
      queue.push({ file, def });
    }
    return name;
  };

  const rewrite = (node: unknown, file: SchemaFile): unknown => {
    if (Array.isArray(node)) return node.map((item) => rewrite(item, file));
    if (node === null || typeof node !== "object") return node;
    const out: JsonObject = {};
    for (const [key, value] of Object.entries(node)) {
      if (key === "$ref" && typeof value === "string") {
        const target = parseRef(absoluteRef(value, file));
        out.$ref = `#/$defs/${localName(target.file, target.def)}`;
      } else {
        out[key] = rewrite(value, file);
      }
    }
    return out;
  };

  const body = rewrite(
    definition(root.file, root.def),
    root.file,
  ) as JsonObject;
  for (let next = queue.shift(); next; next = queue.shift()) {
    defs[localName(next.file, next.def)] = rewrite(
      definition(next.file, next.def),
      next.file,
    );
  }
  return {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    ...body,
    ...(Object.keys(defs).length > 0 ? { $defs: defs } : {}),
  };
}

function definition(file: SchemaFile, def: string): unknown {
  const defs = documents[file].$defs as JsonObject;
  if (!(def in defs)) throw new Error(`Không có ${file}#/$defs/${def}`);
  return defs[def];
}

function parseRef(ref: string): { file: SchemaFile; def: string } {
  const match = ref.match(
    /^([a-z_]+\.schema\.json)#\/\$defs\/([A-Za-z0-9_]+)$/,
  );
  const file = match?.[1] as SchemaFile | undefined;
  if (!match?.[2] || !file || !SCHEMA_FILES.includes(file))
    throw new Error(`Ref schema không hợp lệ: ${ref}`);
  return { file, def: match[2] };
}

/** `#/$defs/X` trong file F thành `F#/$defs/X`; ref đã có tên file giữ nguyên. */
function absoluteRef(ref: string, file: SchemaFile): string {
  return ref.startsWith("#") ? `${file}${ref}` : ref;
}
