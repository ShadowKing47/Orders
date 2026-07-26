"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { getRun, listRunEvents } from "@/lib/api";

const POLL_INTERVAL_MS = 10000;

export default function RunPoller({ runId, currentStatus }: { runId: string; currentStatus: string }) {
  const router = useRouter();
  // Tracks the latest known event id across ticks so a new tool call/memory
  // compaction is detected even when it doesn't change the run's status
  // (e.g. a run that stays RUNNING/SLEEPING throughout the tool call).
  const lastEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (currentStatus === "COMPLETED" || currentStatus === "TERMINATED") {
      // Dead workflows don't need polling.
      return;
    }

    const intervalId = setInterval(async () => {
      const [run, events] = await Promise.all([getRun(runId), listRunEvents(runId)]);
      const latestEventId = events[0]?.id ?? null;

      if (lastEventIdRef.current === null) {
        lastEventIdRef.current = latestEventId;
        return;
      }

      if (run.status !== currentStatus || latestEventId !== lastEventIdRef.current) {
        lastEventIdRef.current = latestEventId;
        router.refresh();
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [runId, currentStatus, router]);

  return null;
}
