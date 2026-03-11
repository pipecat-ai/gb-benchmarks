import { useEffect, useRef, type KeyboardEvent } from "react";
import { prettyJson } from "../format";
import { usePlaybackStore } from "../store/playback";
import type { ReplayStep } from "../types";

function stepSummary(step: ReplayStep): string {
  if (step.tool_name === "move") {
    return `${step.state_before.sector} → ${step.state_after.sector}`;
  }
  if (step.tool_name === "trade") {
    const trade = step.details.trade;
    return `${trade?.trade_type ?? "trade"} ${trade?.quantity ?? "?"} ${trade?.commodity ?? ""}`.trim();
  }
  if (step.tool_name === "recharge_warp_power") {
    return `${step.details.recharge?.units ?? "?"} warp for ${step.details.recharge?.cost ?? "?"} cr`;
  }
  if (step.tool_name === "plot_course") {
    return (step.details.course_path ?? []).join(" → ");
  }
  if (step.tool_name === "finished") {
    return "Mission report submitted";
  }
  if (step.step_type === "turn_failure") {
    return step.failure_class ?? "turn failure";
  }
  return Object.keys(step.args).length > 0 ? prettyJson(step.args) : "No arguments";
}

function statusClass(step: ReplayStep): string {
  if (step.result_status === "error" || step.step_type === "error" || step.step_type === "turn_failure") {
    return "text-rose-200 border-rose-300/20 bg-rose-300/10";
  }
  if (step.tool_name === "trade") {
    return "text-lime-200 border-lime-300/20 bg-lime-300/10";
  }
  if (step.tool_name === "move" || step.tool_name === "plot_course") {
    return "text-cyan-200 border-cyan-300/20 bg-cyan-300/10";
  }
  return "text-slate-200 border-white/10 bg-white/[0.03]";
}

export function ActionLog() {
  const replay = usePlaybackStore((state) => state.replay);
  const currentStepIndex = usePlaybackStore((state) => state.currentStepIndex);
  const setStepIndex = usePlaybackStore((state) => state.setStepIndex);
  const listRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  if (!replay) {
    return null;
  }
  const stepCount = replay.steps.length;

  useEffect(() => {
    const list = listRef.current;
    if (!list || currentStepIndex < 0) {
      return;
    }

    const anchorIndex = Math.max(0, currentStepIndex - 2);
    const anchorItem = itemRefs.current[anchorIndex];
    if (!anchorItem) {
      return;
    }

    const targetTop = Math.max(0, anchorItem.offsetTop - 8);
    list.scrollTo({
      top: targetTop,
      behavior: "smooth",
    });
  }, [currentStepIndex]);

  function focusStep(index: number) {
    itemRefs.current[index]?.focus();
  }

  function handleArrowNavigation(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    let targetIndex: number | null = null;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      targetIndex = Math.min(stepCount - 1, index + 1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      targetIndex = Math.max(0, index - 1);
    }

    if (targetIndex === null || targetIndex === index) {
      return;
    }

    event.preventDefault();
    setStepIndex(targetIndex);
    window.requestAnimationFrame(() => {
      focusStep(targetIndex);
    });
  }

  return (
    <section className="flex h-full min-h-0 max-h-[calc(100vh-8rem)] flex-col overflow-hidden rounded-[28px] border border-white/10 bg-black/30 p-5 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur">
      <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/70">
        Tool Calls And Actions
      </div>
      <div ref={listRef} className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {replay.steps.map((step, index) => {
          const active = step.step_index === currentStepIndex;
          return (
            <button
              key={step.step_index}
              ref={(element) => {
                itemRefs.current[index] = element;
              }}
              onClick={() => setStepIndex(step.step_index)}
              onKeyDown={(event) => handleArrowNavigation(event, index)}
              className={`w-full rounded-[22px] border px-4 py-4 text-left transition ${statusClass(step)} ${
                active ? "ring-2 ring-cyan-300/65" : "hover:border-white/20"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase tracking-[0.24em]">
                  T{String(step.turn_number).padStart(2, "0")}
                  {typeof step.tool_call_index === "number" ? ` · C${step.tool_call_index + 1}` : ""}
                </div>
                <div className="text-[11px] uppercase tracking-[0.22em] opacity-70">
                  {step.result_status ?? step.step_type}
                </div>
              </div>
              <div className="mt-2 text-sm font-semibold text-white">
                {step.tool_name ?? "No tool call"}
              </div>
              <div className="mt-2 text-sm leading-6 opacity-90">
                {stepSummary(step)}
              </div>
              {(step.delta.credits || step.delta.warp) && (
                <div className="mt-3 text-xs uppercase tracking-[0.24em] opacity-75">
                  credits {(step.delta.credits ?? 0) >= 0 ? "+" : ""}
                  {step.delta.credits ?? 0} · warp {(step.delta.warp ?? 0) >= 0 ? "+" : ""}
                  {step.delta.warp ?? 0}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
