export function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export const JSON_HEADERS = { "Content-Type": "application/json" };
