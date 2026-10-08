import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { tryClient, type ClientOptions } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { managedAgentKeys } from "@/lib/agent-management/queries";
import {
  connectionKeys,
  type ConnectionCheck,
} from "@/lib/connections/queries";

const base = "/api/business/admin/connections";
const one = (id: string) => `${base}/${encodeURIComponent(id)}`;
// The agent editor lists the allowed tools, so every change here changes what it offers.
const refresh = (queryClient: QueryClient) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: connectionKeys.all }),
    queryClient.invalidateQueries({ queryKey: managedAgentKeys.all }),
  ]);

/** A refusal here is something the administrator acts on: which agents still use a tool, or why an address was turned down. */
async function ask(
  path: string,
  options: ClientOptions,
  fallback: string,
): Promise<Response> {
  const response = await tryClient(path, {
    ...options,
    headers: businessHeaders(),
  });
  if (response.ok) return response;
  const detail = (await response.json().catch(() => ({}))).detail;
  if (detail?.code === "CONNECTION_IN_USE")
    throw new Error(
      `Agent đang phát hành còn dùng: ${detail.agents.join(", ")}. Thu hồi agent đó hoặc phát hành bản không dùng công cụ này trước.`,
    );
  throw new Error(
    typeof detail === "string" && [409, 422, 502].includes(response.status)
      ? `${fallback} Máy chủ trả lời: ${detail}`
      : fallback,
  );
}

export function createConnectionMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (body: {
      title: string;
      url: string;
      token?: string;
      workspace_id?: string;
      allowed_tools?: string[];
    }): Promise<{ id: string }> =>
      (
        await ask(base, { method: "POST", body }, "Không thêm được kết nối.")
      ).json(),
    onSuccess: () => refresh(queryClient),
  });
}
export function checkConnectionMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (id: string): Promise<ConnectionCheck> =>
      (
        await ask(
          `${one(id)}/check`,
          { method: "POST" },
          "Không kiểm tra được kết nối.",
        )
      ).json(),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: connectionKeys.all }),
  });
}
export function allowConnectionToolsMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async ({
      id,
      names,
      read_names,
    }: {
      id: string;
      names: string[];
      read_names?: string[];
    }): Promise<void> => {
      await ask(
        `${one(id)}/tools`,
        {
          method: "PUT",
          body: { names, ...(read_names ? { read_names } : {}) },
        },
        "Không lưu được công cụ được phép.",
      );
    },
    onSuccess: () => refresh(queryClient),
  });
}
export function removeConnectionMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (id: string): Promise<void> => {
      await ask(one(id), { method: "DELETE" }, "Không xóa được kết nối.");
    },
    onSuccess: () => refresh(queryClient),
  });
}
