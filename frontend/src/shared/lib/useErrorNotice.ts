import { useEffect } from "react";

import { errorMessage } from "./format";
import type { NoticeHandler } from "../model/notice";

export function useErrorNotice(
  onNotice: NoticeHandler,
  ...errors: Array<unknown | null | undefined>
): void {
  const error = errors.find(Boolean);

  useEffect(() => {
    if (error) onNotice(errorMessage(error));
  }, [error, onNotice]);
}
