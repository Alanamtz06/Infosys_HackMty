import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetAllWidgets, toggleWidget, useDraggableWidget } from "./useDraggableWidget";

function storageKey(id: string): string {
  return `lynx-widget:${id}`;
}

/** El hook solo llama `setPointerCapture`/`releasePointerCapture` sobre
 * `event.target`, que jsdom no implementa de forma nativa — un target de
 * mentira con esos dos metodos como no-ops alcanza para probar la logica de
 * arrastre sin simular un DOM real. */
function fakePointerEvent(overrides: Partial<React.PointerEvent>): React.PointerEvent {
  return {
    button: 0,
    pointerId: 1,
    clientX: 0,
    clientY: 0,
    target: { setPointerCapture: vi.fn(), releasePointerCapture: vi.fn() },
    ...overrides,
  } as unknown as React.PointerEvent;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("useDraggableWidget", () => {
  it("defaults to open at (0, 0) when nothing is stored", () => {
    const { result } = renderHook(() => useDraggableWidget("orders"));
    expect(result.current).toMatchObject({ dx: 0, dy: 0, open: true });
  });

  it("reads a previously persisted layout on mount", () => {
    localStorage.setItem(storageKey("orders"), JSON.stringify({ dx: 40, dy: -12, open: false }));
    const { result } = renderHook(() => useDraggableWidget("orders"));
    expect(result.current).toMatchObject({ dx: 40, dy: -12, open: false });
  });

  it("falls back to the default layout when localStorage holds garbage", () => {
    localStorage.setItem(storageKey("orders"), "{ not valid json");
    const { result } = renderHook(() => useDraggableWidget("orders"));
    expect(result.current).toMatchObject({ dx: 0, dy: 0, open: true });
  });

  it("close() hides the widget and persists it", () => {
    const { result } = renderHook(() => useDraggableWidget("orders"));
    act(() => result.current.close());

    expect(result.current.open).toBe(false);
    expect(JSON.parse(localStorage.getItem(storageKey("orders"))!)).toMatchObject({ open: false });
  });

  it("dragging updates dx/dy by the pointer delta and persists on release", () => {
    const { result } = renderHook(() => useDraggableWidget("liveLog"));

    act(() => {
      result.current.dragHandleProps.onPointerDown(fakePointerEvent({ clientX: 100, clientY: 100 }));
    });
    act(() => {
      result.current.dragHandleProps.onPointerMove(fakePointerEvent({ clientX: 130, clientY: 85 }));
    });
    expect(result.current.dx).toBe(30);
    expect(result.current.dy).toBe(-15);

    act(() => {
      result.current.dragHandleProps.onPointerUp(fakePointerEvent({ clientX: 130, clientY: 85 }));
    });
    const saved = JSON.parse(localStorage.getItem(storageKey("liveLog"))!);
    expect(saved).toMatchObject({ dx: 30, dy: -15 });
  });

  it("ignores non-primary pointer buttons (e.g. right-click)", () => {
    const { result } = renderHook(() => useDraggableWidget("liveLog"));

    act(() => {
      result.current.dragHandleProps.onPointerDown(fakePointerEvent({ button: 2, clientX: 50, clientY: 50 }));
    });
    act(() => {
      result.current.dragHandleProps.onPointerMove(fakePointerEvent({ clientX: 200, clientY: 200 }));
    });

    // Sin un pointerDown "real" que arme el arrastre, un pointerMove no debe
    // mover nada.
    expect(result.current.dx).toBe(0);
    expect(result.current.dy).toBe(0);
  });

  it("resetAllWidgets() restores an open widget to the default position", () => {
    const { result } = renderHook(() => useDraggableWidget("orders"));
    act(() => {
      result.current.dragHandleProps.onPointerDown(fakePointerEvent({ clientX: 0, clientY: 0 }));
      result.current.dragHandleProps.onPointerMove(fakePointerEvent({ clientX: 90, clientY: 40 }));
      result.current.dragHandleProps.onPointerUp(fakePointerEvent({ clientX: 90, clientY: 40 }));
    });
    expect(result.current.dx).toBe(90);

    act(() => resetAllWidgets());

    expect(result.current).toMatchObject({ dx: 0, dy: 0, open: true });
  });

  it("resetAllWidgets() also reopens a widget the user had closed", () => {
    const { result } = renderHook(() => useDraggableWidget("orders"));
    act(() => result.current.close());
    expect(result.current.open).toBe(false);

    act(() => resetAllWidgets());

    expect(result.current.open).toBe(true);
  });

  it("toggleWidget(id) only affects the widget with the matching id", () => {
    const orders = renderHook(() => useDraggableWidget("orders"));
    const liveLog = renderHook(() => useDraggableWidget("liveLog"));

    act(() => toggleWidget("orders"));

    expect(orders.result.current.open).toBe(false);
    expect(liveLog.result.current.open).toBe(true);
  });

  it("toggleWidget(id) flips open back to true on a second call", () => {
    const { result } = renderHook(() => useDraggableWidget("orders"));

    act(() => toggleWidget("orders"));
    expect(result.current.open).toBe(false);

    act(() => toggleWidget("orders"));
    expect(result.current.open).toBe(true);
  });
});
