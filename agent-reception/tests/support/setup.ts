// Unit/capability tests must not send traces when the developer's shell has
// LangSmith enabled. Production observability remains a PH05 concern.
process.env.LANGSMITH_TRACING = "false";
process.env.LANGCHAIN_TRACING_V2 = "false";
process.env.LANGCHAIN_TRACING = "false";
