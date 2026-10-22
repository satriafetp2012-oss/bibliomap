import { useCallback, useEffect, useState } from "react";

import { workspaceApi } from "./api";
import type { WorkspaceSummary } from "./types";

const STORAGE_KEY = "bibliomap.workspaceId";

/** Workspace id from ?ws=, else the last one used, else a fresh workspace. */
function idFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("ws");
}

function rememberId(id: string) {
  localStorage.setItem(STORAGE_KEY, id);
  const url = new URL(window.location.href);
  if (url.searchParams.get("ws") !== id) {
    url.searchParams.set("ws", id);
    window.history.replaceState(null, "", url);
  }
}

export function useWorkspace() {
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async (id: string) => {
    const next = await workspaceApi.summary(id);
    setSummary(next);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function start() {
      const candidate = idFromUrl() ?? localStorage.getItem(STORAGE_KEY);
      if (candidate) {
        try {
          const found = await workspaceApi.summary(candidate);
          if (cancelled) return;
          setSummary(found);
          rememberId(candidate);
          return;
        } catch {
          // A stale or foreign id: fall through and start a new workspace.
          if (!cancelled) setNotice("workspace.notFound");
        }
      }
      const created = await workspaceApi.create();
      if (cancelled) return;
      rememberId(created.id);
      await refresh(created.id);
    }
    void start();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  const reload = useCallback(async () => {
    if (summary) await refresh(summary.workspace.id);
  }, [summary, refresh]);

  const startNew = useCallback(async () => {
    const created = await workspaceApi.create();
    rememberId(created.id);
    setNotice(null);
    await refresh(created.id);
  }, [refresh]);

  return { summary, notice, reload, startNew };
}
