/** Minimal toast system (docs/15 §7): success / error / conflict, auto-dismiss. */

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type ToastKind = "success" | "error" | "conflict";

interface ToastItem {
  id: number;
  kind: ToastKind;
  text: string;
}

const ToastContext = createContext<((kind: ToastKind, text: string) => void) | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, kind, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 4000);
  }, []);

  const styles: Record<ToastKind, string> = {
    success: "bg-green-700",
    error: "bg-red-700",
    conflict: "bg-amber-700",
  };

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 flex-col gap-2">
        {toasts.map((item) => (
          <div
            key={item.id}
            role="status"
            className={`rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${styles[item.kind]}`}
          >
            {item.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast outside ToastProvider");
  return push;
}
