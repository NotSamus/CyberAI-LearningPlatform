"use client";
import { useEffect, useState } from "react";
import { dayKey } from "@/lib/dates";

// Today, in the viewer's own time zone, or null until the page is in the browser (the server's day
// may be another one). It moves on by itself at midnight, and when the page is come back to after
// the computer slept, so a page left open overnight shows the new day.
export function useToday(): Date | null {
  const [today, setToday] = useState<Date | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const check = () => {
      clearTimeout(timer);
      const now = new Date();
      setToday((shown) => (shown && dayKey(shown) === dayKey(now) ? shown : now));
      const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
      timer = setTimeout(check, midnight.getTime() - now.getTime() + 1000);
    };
    const back = () => {
      if (document.visibilityState === "visible") check();
    };
    check();
    document.addEventListener("visibilitychange", back);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", back);
    };
  }, []);
  return today;
}
