import type {
  AgentCreationRequest,
  FactoryCatalogueProjection,
} from "../../../agent-factory/src/contracts.js";
import {
  parametersFor,
  REFUSAL_MARKER,
  type GrantedTool,
} from "../../src/plugins/tools.js";
import { toolNameFor } from "../../src/plugins/store.js";

export const RAG = "platform/rag_query";
const tool = (
  ref: string,
  description: string,
  argument: string,
  effect: "read" | "write" = "read",
) => ({
  kind: "tool" as const,
  ref,
  name: ref.split("/")[1]!,
  title: ref.split("/")[0]!,
  description,
  inputSchema: {
    type: "object",
    properties: { [argument]: { type: "string", minLength: 1 } },
    required: [argument],
    additionalProperties: false,
  },
  outputSchema: null,
  effect,
  destructive: effect === "write",
});
export const catalogue: FactoryCatalogueProjection = {
  tools: [
    tool(
      "web/search",
      "Search public information on the Internet. Returns title, URL and excerpt for each source.",
      "query",
    ),
    tool(
      "incident/search",
      "Search security incidents by query, status or location. Returns incident IDs and status summaries.",
      "query",
    ),
    tool(
      "incident/get",
      "Read details and handling status of one security incident by its user-supplied ID.",
      "id",
    ),
    tool(
      "incident/close",
      "Close an incident, changing its status.",
      "id",
      "write",
    ),
    tool(
      "crm/get_customer",
      "Read customer details from the CRM using the user-supplied customer ID.",
      "id",
    ),
    tool(
      "calendar/list_events",
      "Read calendar events matching the user's requested date or topic.",
      "query",
    ),
    tool(
      RAG,
      "Retrieve relevant passages and document identifiers from internal policies, knowledge and SOP documents.",
      "query",
    ),
  ],
  skills: [],
  defaultToolRefs: [RAG],
};
export type Clause = { id: string; pattern: string };
export type RagUsage = "required" | "optional" | "unnecessary";
export interface ConstructionCase {
  id: string;
  category: string;
  input: AgentCreationRequest;
  expected: {
    requiredTools: string[];
    allowedTools: string[];
    forbiddenTools: string[];
    defaultTools: string[];
    expectedCapabilities: Clause[];
    expectedSkillClauses: Clause[];
    forbiddenSkillClauses: Clause[];
    expectedRagUsage: RagUsage;
    expectedConstruction: "PASS" | "NEEDS_INPUT" | "FAIL";
  };
}
const clause = (id: string, pattern: string): Clause => ({ id, pattern });
const makeCase = (
  id: string,
  category: string,
  name: string,
  role: string,
  description: string,
  required: string[],
  patterns: string[],
  rag: RagUsage = "unnecessary",
): ConstructionCase => ({
  id,
  category,
  input: { name, role, description },
  expected: {
    requiredTools: required,
    allowedTools: required,
    forbiddenTools: catalogue.tools
      .map((t) => t.ref)
      .filter((ref) => !required.includes(ref) && ref !== RAG),
    defaultTools: [RAG],
    expectedCapabilities: patterns.map((p, i) =>
      clause(`capability-${i + 1}`, p),
    ),
    expectedSkillClauses: patterns.map((p, i) => clause(`skill-${i + 1}`, p)),
    forbiddenSkillClauses: [
      clause(
        "unrequested-write",
        "(?<!not )(?<!never )(?<!don't )(?:close|delete|update|send) (?:the |an? |all )?(?:incident|customer|email|record)",
      ),
    ],
    expectedRagUsage: rag,
    expectedConstruction: category === "ambiguous" ? "NEEDS_INPUT" : "PASS",
  },
});
export const cases: ConstructionCase[] = [
  makeCase(
    "L01",
    "no-special-tool",
    "Tóm tắt",
    "Summarizer",
    "Tóm tắt nội dung người dùng cung cấp, giữ đúng ý chính và không bổ sung thông tin ngoài văn bản.",
    [],
    ["summari|tóm tắt", "supplied|provided|cung cấp|văn bản"],
  ),
  makeCase(
    "L02",
    "no-special-tool",
    "Translator",
    "Text translator",
    "Translate text supplied by the user into their requested language, preserving meaning.",
    [],
    ["translat|dịch", "meaning|nghĩa"],
  ),
  makeCase(
    "L03",
    "no-special-tool",
    "Classifier",
    "Text classifier",
    "Classify supplied text using categories supplied by the user and explain the category choice.",
    [],
    ["classif|phân loại", "categor|nhãn"],
  ),
  makeCase(
    "L04",
    "no-special-tool",
    "Reviewer",
    "Text reviewer",
    "Review supplied text for spelling and clarity and suggest edits without changing its meaning.",
    [],
    ["spell|spelling|chính tả", "clarity|clear|rõ"],
  ),
  makeCase(
    "L05",
    "no-special-tool",
    "Writer",
    "Text writer",
    "Draft text using only the user's supplied brief and facts; ask for any missing brief details.",
    [],
    ["draft|write|viết", "brief|supplied|provided"],
  ),
  makeCase(
    "L06",
    "one-tool",
    "Web Researcher",
    "Internet Research Agent",
    "Tìm kiếm thông tin trên Internet và tổng hợp câu trả lời có dẫn nguồn URL.",
    ["web/search"],
    ["search|tìm kiếm", "citat|cite|source|dẫn nguồn"],
  ),
  makeCase(
    "L07",
    "one-tool",
    "Incident lookup",
    "Incident lookup assistant",
    "Search security incidents using a user-supplied query and summarize matching statuses. Do not change records.",
    ["incident/search"],
    ["incident", "status"],
  ),
  makeCase(
    "L08",
    "one-tool",
    "Customer lookup",
    "CRM reader",
    "Read the CRM customer record for an ID supplied by the user and summarize customer details without changing data.",
    ["crm/get_customer"],
    ["customer", "summari|detail"],
  ),
  makeCase(
    "L09",
    "one-tool",
    "Calendar lookup",
    "Calendar reader",
    "Read calendar events matching the user's supplied date or topic and summarize the schedule without creating events.",
    ["calendar/list_events"],
    ["calendar|event", "summari|schedule"],
  ),
  makeCase(
    "L10",
    "one-tool",
    "Document retrieval",
    "Internal document reader",
    "Retrieve internal documents relevant to the user's question and summarize passages with document references.",
    [RAG],
    ["retriev|search|query", "document|passage"],
    "required",
  ),
  makeCase(
    "L11",
    "multi-tool",
    "Incident investigator",
    "Incident status assistant",
    "Tra cứu incident bằng truy vấn người dùng cung cấp và đọc chi tiết incident theo ID người dùng cung cấp để tổng hợp trạng thái. Chỉ đọc, không thay đổi dữ liệu.",
    ["incident/search", "incident/get"],
    ["incident", "status|trạng thái"],
  ),
  makeCase(
    "L12",
    "multi-tool",
    "Customer research",
    "Customer research analyst",
    "Read the CRM customer record by user-supplied ID, research that company on the public Internet using the company name supplied by the user, and synthesize a report citing web URLs. Read only.",
    ["crm/get_customer", "web/search"],
    ["customer|crm", "web|internet|public", "report|synthesi|citat|cite"],
  ),
  makeCase(
    "L13",
    "multi-tool",
    "Support analyst",
    "Support analyst",
    "Read a customer record by user-supplied CRM ID and retrieve internal support policies relevant to the supplied question. Summarize the customer context and the documented policy without changing records.",
    ["crm/get_customer", RAG],
    ["customer", "polic|internal"],
    "required",
  ),
  makeCase(
    "L14",
    "multi-tool",
    "Report preparation",
    "Report preparer",
    "Search public Internet information for the user's topic, retrieve internal documents for that same topic, and produce a report distinguishing public URL sources from internal document references.",
    ["web/search", RAG],
    ["public|web|internet", "internal|document", "report"],
    "required",
  ),
  makeCase(
    "L15",
    "multi-tool",
    "Operational assistant",
    "Read-only operations assistant",
    "Read calendar events for the user's supplied date and search security incidents for the user's supplied location. Summarize the schedule and incident statuses without taking actions.",
    ["calendar/list_events", "incident/search"],
    ["calendar|event|schedule", "incident", "status|summari"],
  ),
  makeCase(
    "L16",
    "rag-focused",
    "Internal Policy Assistant",
    "Internal Policy Assistant",
    "Trả lời câu hỏi theo tài liệu chính sách nội bộ, dẫn tài liệu hỗ trợ và nói rõ khi không có bằng chứng.",
    [RAG],
    [
      "polic|chính sách",
      "retriev|query|search|truy|tìm",
      "evidence|support|bằng chứng|tài liệu",
    ],
    "required",
  ),
  makeCase(
    "L17",
    "rag-focused",
    "Knowledge assistant",
    "Internal knowledge assistant",
    "Answer the user's question using retrieved internal knowledge documents; cite supporting documents and say when documents do not cover an answer.",
    [RAG],
    ["internal|knowledge", "retriev|query|search", "document|cite"],
    "required",
  ),
  makeCase(
    "L18",
    "rag-focused",
    "SOP assistant",
    "SOP assistant",
    "Retrieve internal SOP documents for the user's process and explain the documented steps with references; do not perform the process or invent steps.",
    [RAG],
    ["sop|procedure|process", "retriev|query|search", "step|reference"],
    "required",
  ),
  makeCase("L19", "ambiguous", "Trợ lý", "Trợ lý", "Trợ lý", [], []),
  makeCase(
    "L20",
    "ambiguous",
    "Hỗ trợ công việc",
    "Hỗ trợ công việc",
    "Hỗ trợ công việc",
    [],
    [],
  ),
];

export interface BehaviorCase {
  id: string;
  constructionId: string;
  prompt: string;
  expectedTools: string[];
  allowedTools: string[];
  forbiddenTools: string[];
  expectedRagUsage: RagUsage;
  outputClauses: Clause[];
  maxCalls: number;
}
const behavior = (
  id: string,
  constructionId: string,
  prompt: string,
  tools: string[],
  patterns: string[],
  rag: RagUsage = "unnecessary",
): BehaviorCase => ({
  id,
  constructionId,
  prompt,
  expectedTools: tools,
  allowedTools: tools,
  forbiddenTools: catalogue.tools
    .map((t) => t.ref)
    .filter((ref) => !tools.includes(ref)),
  expectedRagUsage: rag,
  outputClauses: patterns.map((p, i) => clause(`output-${i + 1}`, p)),
  maxCalls: Math.max(1, tools.length * 2),
});
export const behaviors = [
  behavior(
    "B01",
    "L06",
    "Research the Helios battery recycling pilot and summarize its findings with source URLs.",
    ["web/search"],
    ["helios", "82", "https://sources\\.example/helios"],
  ),
  behavior(
    "B02",
    "L01",
    "Tóm tắt: Dự án Sao Mai thử nghiệm tại Đà Nẵng với 12 nhân viên. Chi phí giảm 18%. Nhóm sẽ đánh giá lại vào tháng 11.",
    [],
    ["Sao Mai", "12", "18", "11"],
  ),
  behavior(
    "B03",
    "L16",
    "According to our internal travel policy, what is the hotel reimbursement limit, who approves exceptions, and is a taxi allowance documented?",
    [RAG],
    [
      "137",
      "director",
      "taxi",
      "not|no |không|doesn.t|undocumented|unspecified",
    ],
    "required",
  ),
  behavior(
    "B04",
    "L11",
    "Search security incidents matching Warehouse A and read details for incident ID INC-104. Summarize its handling status. Do not close it.",
    ["incident/search", "incident/get"],
    ["INC-104", "investigat", "sensor"],
  ),
  behavior(
    "B05",
    "L12",
    "Read CRM customer ID C-042. Research the public Helios battery recycling pilot using the company name Helios supplied here. Synthesize the customer context and public findings with URLs. Read only.",
    ["crm/get_customer", "web/search"],
    ["Helios", "enterprise", "82", "https://sources\\.example/helios"],
  ),
];
export const mockResults: Record<string, unknown> = {
  "web/search": {
    results: [
      {
        title: "Helios pilot results",
        url: "https://sources.example/helios",
        content:
          "Helios battery recycling pilot recovered 82% of materials in its trial.",
      },
      {
        title: "Helios pilot limitations",
        url: "https://sources.example/helios-limits",
        content:
          "The Helios battery pilot was a small trial; industrial scale performance is not yet established.",
      },
    ],
  },
  "incident/search": {
    incidents: [
      {
        id: "INC-104",
        location: "Warehouse A",
        status: "investigating",
        title: "Sensor alert",
      },
    ],
  },
  "incident/get": {
    id: "INC-104",
    location: "Warehouse A",
    status: "investigating",
    detail: "Sensor malfunction under investigation; no confirmed intrusion.",
    assignee: "Mina",
  },
  "crm/get_customer": {
    id: "C-042",
    name: "Helios",
    tier: "enterprise",
    contact: "Nia",
  },
  "calendar/list_events": {
    events: [{ title: "Operations review", date: "2026-10-05" }],
  },
  [RAG]: {
    documents: [
      {
        id: "TRAVEL-7",
        title: "Internal travel policy",
        passage:
          "Hotel reimbursement is capped at USD 137 per night. Exceptions require director approval. This document does not specify a taxi allowance.",
      },
    ],
  },
};
export interface ToolCall {
  toolRef: string;
  arguments: unknown;
  order: number;
  argumentsValid: boolean;
  authorized: boolean;
  result: string;
}

/** Test-only access facts; selected tools never implicitly grant themselves. */
export function evalTools(
  selected: readonly string[],
  grants: Set<string>,
  calls: ToolCall[],
): GrantedTool[] {
  return catalogue.tools
    .filter(
      (t) =>
        selected.includes(t.ref) && grants.has(t.ref) && t.effect === "read",
    )
    .map((t) => {
      const parameters = parametersFor(t.inputSchema);
      return {
        ref: t.ref,
        name: toolNameFor(t.ref),
        description: t.description,
        parameters,
        execute: async (args) => {
          const argumentsValid = parameters.safeParse(args).success;
          const authorized = grants.has(t.ref); // Recheck a grant revoked after the offer.
          const result = !authorized
            ? `${REFUSAL_MARKER} Missing eval grant.`
            : !argumentsValid
              ? "Invalid tool arguments."
              : JSON.stringify(mockResults[t.ref]);
          calls.push({
            toolRef: t.ref,
            arguments: args,
            order: calls.length + 1,
            argumentsValid,
            authorized,
            result,
          });
          return result;
        },
      };
    });
}
