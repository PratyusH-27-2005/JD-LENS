"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api";

type State<T> =
  | { key: string; status: "ok"; data: T }
  | { key: string; status: "error"; error: ApiError };

/**
 * Loads `fn()` whenever `key` changes, with loading / error / data states.
 * Loading is derived (the last result belongs to a different key), so no state is set
 * synchronously inside the effect.
 */
export function useAsync<T>(fn: () => Promise<T>, key: string) {
  const [nonce, setNonce] = useState(0);
  const requestKey = `${key}#${nonce}`;
  const [state, setState] = useState<State<T> | null>(null);

  useEffect(() => {
    let cancelled = false;
    fn().then(
      (data) => !cancelled && setState({ key: requestKey, status: "ok", data }),
      (e: unknown) =>
        !cancelled &&
        setState({
          key: requestKey,
          status: "error",
          error: e instanceof ApiError ? e : new ApiError(0, "unknown", String(e)),
        }),
    );
    return () => {
      cancelled = true;
    };
    // `fn` is recreated every render; `requestKey` is what identifies the request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const current = state?.key === requestKey ? state : null;
  // Keep showing the previous data while reloading (no flash of skeleton).
  const data = current?.status === "ok" ? current.data : state?.status === "ok" ? state.data : null;

  return {
    data,
    error: current?.status === "error" ? current.error : null,
    loading: current === null,
    reload,
    /** Replace the data locally, e.g. with a mutation's response. */
    setData: (next: T) => setState({ key: requestKey, status: "ok", data: next }),
  };
}
