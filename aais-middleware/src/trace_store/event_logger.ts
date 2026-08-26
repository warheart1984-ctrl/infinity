/**
 * Mythic: Trace event logger
 * Engineering: EventLogger + singleton eventLogger
 */
import { randomUUID } from "node:crypto";
import type { ProviderCallEvent, ReplayTrace } from "./interfaces.js";

export class EventLogger {
  private events: ProviderCallEvent[] = [];

  log(
    partial: Omit<ProviderCallEvent, "id" | "timestamp"> & {
      id?: string;
      timestamp?: string;
    },
    trace?: ReplayTrace,
  ): ProviderCallEvent {
    const event: ProviderCallEvent = {
      id: partial.id ?? `evt_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
      requestId: partial.requestId,
      provider: partial.provider,
      lane: partial.lane,
      input: partial.input,
      output: partial.output,
      error: partial.error,
      timestamp: partial.timestamp ?? new Date().toISOString(),
    };
    this.events.push(event);
    if (trace) {
      trace.events.push(event);
    }
    return event;
  }

  all(): ProviderCallEvent[] {
    return [...this.events];
  }

  clear(): void {
    this.events = [];
  }
}

export const eventLogger = new EventLogger();
