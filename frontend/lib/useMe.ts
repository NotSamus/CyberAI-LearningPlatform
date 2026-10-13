"use client";
import { useEffect, useState } from "react";
import { api, type Me } from "@/lib/api";

// The logged-in account, or null while loading. Only used to decide what to show: the server
// checks the account again on every request.
export function useMe(): Me | null {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    api<Me>("/me").then(setMe).catch(() => setMe(null));
  }, []);
  return me;
}
