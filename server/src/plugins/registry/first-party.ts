import type { ToolDescriptor } from "./types";
import { validateToolDescriptors } from "./validation";

/**
 * First-party business tools exposed by this deployment.
 *
 * Reporting, knowledge, technical, and other business modules add their
 * descriptors to this list. Implementations remain in their owning modules;
 * only reviewed metadata and handler references belong in this registry.
 */
const descriptors: readonly ToolDescriptor[] = [];

export const FIRST_PARTY_TOOLS = validateToolDescriptors(descriptors);
