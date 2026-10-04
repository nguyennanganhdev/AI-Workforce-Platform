/**
 * Prints the technical tool catalogue as JSON, for scripts that register it in a tenant's
 * tool catalogue (services/vinhomes-api/scripts/setup_session_tools.py).
 *
 *   cd server && bun scripts/print_technical_tools.ts
 */
import { describeTechnicalTools } from "../src/technical-tools";

console.log(JSON.stringify(describeTechnicalTools()));
