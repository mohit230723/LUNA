import { RunEvent } from '../contract';

export interface MockSubscriptionOptions {
  lastEventId?: number;
  onEvent: (e: RunEvent) => void;
  onState: (s: 'open' | 'reconnecting' | 'closed') => void;
}

export function createMockEventSource(
  events: RunEvent[],
  opts: MockSubscriptionOptions,
  speedMultiplier = 1
): () => void {
  let isCancelled = false;
  let timerId: ReturnType<typeof setTimeout> | null = null;
  const lastId = opts.lastEventId ?? 0;

  // Filter events to only those after lastEventId
  const pendingEvents = events.filter((e) => e.seq > lastId);

  // Speed calculation: 0 = instant (synchronous microtasks for tests)
  const baseInterval = speedMultiplier === 0 ? 0 : Math.max(20, Math.floor(350 / speedMultiplier));

  opts.onState('open');

  let currentIndex = 0;

  function scheduleNext() {
    if (isCancelled || currentIndex >= pendingEvents.length) {
      if (!isCancelled) {
        opts.onState('closed');
      }
      return;
    }

    const event = pendingEvents[currentIndex]!;
    currentIndex++;

    if (baseInterval === 0) {
      opts.onEvent(event);
      scheduleNext();
    } else {
      timerId = setTimeout(() => {
        if (isCancelled) return;
        opts.onEvent(event);
        scheduleNext();
      }, baseInterval);
    }
  }

  // Start emitting
  scheduleNext();

  return () => {
    isCancelled = true;
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
    opts.onState('closed');
  };
}
