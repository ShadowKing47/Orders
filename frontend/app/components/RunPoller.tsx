"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getRun } from "@/lib/api";

const POLL_INTERVAL_MS = 10000;

export default function RunPoller({ runId, currentStatus }: { runId: string; currentStatus: string }) {
  const router = useRouter();

  useEffect(() => {
    if (currentStatus === "COMPLETED" || currentStatus === "TERMINATED") {
      // Dead workflows don't need polling.
      return;
    }

    const intervalId = setInterval(async () => {
      const run = await getRun(runId);
      if (run.status !== currentStatus) {
        router.refresh();
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [runId, currentStatus, router]);

  return null;
}
