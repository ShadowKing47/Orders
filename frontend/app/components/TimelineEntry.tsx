"use client";

import { useState } from "react";

const TRUNCATE_LENGTH = 110;

export default function TimelineEntry({ label, time, detail }: { label: string; time: string; detail: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = detail.length > TRUNCATE_LENGTH;
  const shown = expanded || !isLong ? detail : `${detail.slice(0, TRUNCATE_LENGTH)}…`;

  return (
    <li className="py-2.5 first:pt-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-on-surface">{label}</span>
        <span className="text-[10px] font-mono text-on-surface-variant whitespace-nowrap">{time}</span>
      </div>
      {detail && (
        <button
          type="button"
          onClick={() => isLong && setExpanded((prev) => !prev)}
          className={`text-[11px] font-mono text-on-surface-variant mt-0.5 text-left ${
            isLong ? "cursor-pointer hover:text-on-surface" : "cursor-default"
          } ${expanded ? "whitespace-pre-wrap" : "truncate w-full"}`}
        >
          {shown}
          {isLong && !expanded && <span className="text-secondary font-bold"> show more</span>}
        </button>
      )}
    </li>
  );
}
