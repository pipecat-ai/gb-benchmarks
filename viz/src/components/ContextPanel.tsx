import { formatMessageContent, prettyJson } from "../format";
import { getCurrentTurn, getInferenceInputForStep, usePlaybackStore } from "../store/playback";
import type { ContextMessage } from "../types";

function roleClass(role: string): string {
  if (role === "assistant") {
    return "border-cyan-300/25 bg-cyan-300/10";
  }
  if (role === "tool") {
    return "border-lime-300/25 bg-lime-300/10";
  }
  return "border-white/10 bg-white/[0.03]";
}

function MessageCard({ message }: { message: ContextMessage }) {
  return (
    <div className={`rounded-2xl border px-4 py-3 ${roleClass(message.role)}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-200/75">
        {message.role}
      </div>
      <pre className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-100/88">
        {formatMessageContent(message)}
      </pre>
    </div>
  );
}

function formatToolRequests(
  toolSteps: Array<{
    tool_name?: string | null;
    args: Record<string, unknown>;
    tool_call_index?: number | null;
  }>,
): string {
  if (toolSteps.length === 0) {
    return "(no tool requests)";
  }

  return toolSteps
    .map((step) => {
      const label =
        typeof step.tool_call_index === "number"
          ? `call ${step.tool_call_index + 1}`
          : "call";
      return `${label}: ${step.tool_name ?? "unknown"}\n${prettyJson(step.args)}`;
    })
    .join("\n\n");
}

export function ContextPanel() {
  const replay = usePlaybackStore((state) => state.replay);
  const currentStepIndex = usePlaybackStore((state) => state.currentStepIndex);

  if (!replay) {
    return null;
  }

  const turn = getCurrentTurn(replay, currentStepIndex);
  const inferenceInput = getInferenceInputForStep(replay, currentStepIndex);
  const messages = inferenceInput?.messages_for_llm ?? inferenceInput?.messages ?? [];
  const recentMessages = messages.slice(Math.max(0, messages.length - 6));
  const toolRequests =
    turn != null
      ? replay.steps
          .slice(turn.step_start_index, turn.step_end_index + 1)
          .filter((step) => step.tool_name)
      : [];

  return (
    <section className="flex h-full min-h-0 max-h-[calc(100vh-8rem)] flex-col overflow-hidden rounded-[28px] border border-white/10 bg-black/30 p-5 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur">
      <div className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/70">
        Inference Context
      </div>

      {!inferenceInput || !turn ? (
        <div className="mt-4 rounded-2xl border border-dashed border-white/10 bg-white/[0.03] px-4 py-5 text-sm text-slate-300/75">
          Context unavailable for this step. Runs without <code>capture_inference_inputs</code> replay the map
          and tool log, but not the message history.
        </div>
      ) : (
        <>
          <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-4 text-xs uppercase tracking-[0.24em] text-slate-300/65">
            Inference {inferenceInput.inference_index} · reasons {(inferenceInput.reasons ?? []).join(", ") || "—"}
          </div>

          <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
            {recentMessages.map((message, index) => (
              <MessageCard key={`${message.role}-${index}`} message={message} />
            ))}

            <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/65 px-4 py-4">
              {toolRequests.length > 0 && (
                <>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-300/70">
                    Assistant Tool Requests
                  </div>
                  <pre className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-100/90">
                    {formatToolRequests(toolRequests)}
                  </pre>
                </>
              )}
              <div className="mt-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-300/70">
                LLM Response Text
              </div>
              <pre className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-100/90">
                {turn.raw_response_text?.trim() || "(no assistant text; tool-call-only turn)"}
              </pre>
              {turn.raw_thought_text && (
                <>
                  <div className="mt-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-300/70">
                    Raw Thought
                  </div>
                  <pre className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300/90">
                    {turn.raw_thought_text}
                  </pre>
                </>
              )}
            </div>

            <details className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-4">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.24em] text-slate-200/75">
                Expand Full Context
              </summary>
              <div className="mt-4 space-y-3">
                {messages.map((message, index) => (
                  <MessageCard key={`full-${message.role}-${index}`} message={message} />
                ))}
              </div>
              <div className="mt-4 rounded-2xl border border-white/8 bg-slate-950/65 px-4 py-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-300/70">
                  Provider Invocation Params
                </div>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-300/85">
                  {prettyJson(inferenceInput.provider_invocation_params ?? {})}
                </pre>
              </div>
            </details>
          </div>
        </>
      )}
    </section>
  );
}
