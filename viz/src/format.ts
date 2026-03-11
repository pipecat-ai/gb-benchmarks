import type { ContextMessage } from "./types";

export function formatNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat().format(value);
}

export function formatSignedNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return `${value >= 0 ? "+" : ""}${new Intl.NumberFormat().format(value)}`;
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function formatMessageContent(message: ContextMessage): string {
  if (Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
    return message.tool_calls
      .map((call) => {
        const name = call.function?.name ?? call.type ?? "tool_call";
        return `${name}(${call.function?.arguments ?? ""})`;
      })
      .join("\n");
  }

  const { content } = message;
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (!item || typeof item !== "object") {
          return String(item);
        }
        const typed = item as Record<string, unknown>;
        if (typed.type === "text" && typeof typed.text === "string") {
          return typed.text;
        }
        return JSON.stringify(item);
      })
      .join("\n");
  }
  if (content == null) {
    return "";
  }
  return prettyJson(content);
}
