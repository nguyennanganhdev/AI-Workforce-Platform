import { runEvaluation } from "../tests/agent-factory-eval/runner.js";

if (import.meta.main) process.exitCode = (await runEvaluation()).pass ? 0 : 1;
