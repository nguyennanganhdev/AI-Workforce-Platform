import { createContext, useContext } from 'react';

import type { UploadTask } from './uploadTypes';
import type { KnowledgeDocumentStatus } from '@/api';

/**
 * Public contract the surrounding app sees. Exposed via the React
 * context value.
 */
export interface UploadContextValue {
	tasks: UploadTask[];
	/** Enqueue one or more files against a knowledge base. */
	enqueue: (knowledgeBaseId: string, files: File[]) => UploadTask[];
	/**
	 * Abort an upload task. Effects depend on the current phase:
	 *
	 * - `queued` — removed from the queue.
	 * - `uploading` — XHR is aborted, then the task transitions to
	 *   `cancelled`.
	 * - server-side phases — no-op (the worker has already taken over;
	 *   route through the regular document-delete flow instead).
	 * - terminal phases — equivalent to `dismiss`.
	 */
	cancel: (taskId: string) => void;
	/** Drop a terminal task from the list (UI dismissal). */
	dismiss: (taskId: string) => void;
	/** Drop every terminal task for a knowledge base. */
	clearFinishedForKb: (knowledgeBaseId: string) => void;
	/**
	 * Filtered tasks for a knowledge base id. Cached by reference per
	 * (knowledgeBaseId, tasks-list-identity) so consumers can pass it
	 * straight into React dependency arrays.
	 */
	tasksForKb: (knowledgeBaseId: string) => UploadTask[];
	/**
	 * Apply server-side status snapshots from the polling hook.
	 * Lookup is keyed by `documentId`; tasks without a documentId
	 * (still uploading) are skipped.
	 */
	applyServerStatuses: (
		knowledgeBaseId: string,
		items: Array<{
			id: string;
			status: KnowledgeDocumentStatus;
			error: string | null;
		}>,
	) => void;
	/**
	 * Document ids the consumer should be polling. Filtered to tasks
	 * that have a documentId AND a non-terminal server-side phase.
	 */
	pollableDocumentIds: (knowledgeBaseId: string) => string[];
}

export const UploadContext = createContext<UploadContextValue | null>(null);

export function useUploadContext(): UploadContextValue {
	const ctx = useContext(UploadContext);
	if (!ctx) {
		throw new Error('useUploadContext must be used inside <UploadProvider>');
	}
	return ctx;
}
