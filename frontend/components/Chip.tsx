import type { LucideIcon } from "lucide-react";

// good: done, published. info: in progress. neutral: not started, a draft. warn: soon, or changes
// waiting. bad: late, failed. Always a word too: the colour is never the only sign.
export type Tone = "good" | "info" | "neutral" | "warn" | "bad";

export default function Chip({ tone = "neutral", icon: Icon, title, children }: {
  tone?: Tone;
  icon?: LucideIcon;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <span className={`chip ${tone}`} title={title}>
      {Icon && <Icon aria-hidden />}
      {children}
    </span>
  );
}
