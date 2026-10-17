import type { ToolResultBlock } from '@agentscope-ai/agentscope/message';

/**
 * Flatten a tool result's ``output`` (string or block array) into plain text,
 * keeping only the text blocks. Returns ``''`` when the result is missing.
 */
export function getResultText(result?: ToolResultBlock): string {
	if (!result) return '';
	if (typeof result.output === 'string') return result.output;
	if (Array.isArray(result.output)) {
		return result.output.map((b) => (b.type === 'text' ? b.text : '')).join('\n');
	}
	return '';
}

/**
 * Parse the input arguments from the given string.
 * @param input
 * @returns The JSON Record or empty object if parsing fails.
 */
export function parseInput(input: string): Record<string, unknown> {
	try {
		const parsed = JSON.parse(input);
		return parsed && typeof parsed === 'object' ? parsed : {};
	} catch {
		return {};
	}
}

/**
 * Get the filepath from the input arguments.
 * @param input
 * @returns The filepath, or ``undefined`` when ``input`` isn't yet a complete
 * JSON object carrying a non-empty ``file_path`` — a tool call's arguments
 * stream in as partial JSON, and a fragment of ``content`` must never pass for
 * a path.
 */
export function tryGetFilePath(input: string): string | undefined {
	const { file_path } = parseInput(input) as { file_path?: unknown };
	return typeof file_path === 'string' && file_path.length > 0 ? file_path : undefined;
}

/**
 * The basename of ``file_path``, or ``undefined`` while the tool-call JSON is
 * still streaming. Use this in ``renderHeader`` so a partial input renders no
 * file name rather than a garbled one.
 * @param input
 * @returns The filename, considering different OS path separators.
 */
export function tryGetFileName(input: string): string | undefined {
	const filePath = tryGetFilePath(input);
	if (!filePath) return undefined;
	const segments = filePath.split(/[/\\]+/).filter(Boolean);
	return segments.length > 0 ? segments[segments.length - 1] : filePath;
}

/**
 * Tally inserted / deleted lines from a unified diff text. The leading
 * ``+++`` / ``---`` lines (file headers) are excluded.
 */
export function countDiffStats(diffText: string): {
	insertions: number;
	deletions: number;
} {
	let insertions = 0;
	let deletions = 0;
	for (const line of diffText.split('\n')) {
		if (line.startsWith('+') && !line.startsWith('+++')) insertions++;
		else if (line.startsWith('-') && !line.startsWith('---')) deletions++;
	}
	return { insertions, deletions };
}

/**
 * Extract the ``diff`` field from a ToolResultBlock metadata bag, returning
 * ``undefined`` when missing or empty so callers can use it with ``??``.
 */
export function getResultDiff(result: { metadata?: Record<string, unknown> }): string | undefined {
	const diff = result.metadata?.diff;
	return typeof diff === 'string' && diff.length > 0 ? diff : undefined;
}
