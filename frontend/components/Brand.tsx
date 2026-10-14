import { useId } from "react";

// The logo: a shield (security) with a spark in it (AI), on a square that runs from blue to navy,
// and the name beside it. The spark is cyan, which is only ever used on navy. A theme can change
// these colours (--mark-from, --mark-to, --spark: app/styles/themes.css).
export default function Brand() {
  const fill = useId();
  return (
    <>
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <defs>
          <linearGradient id={fill} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" style={{ stopColor: "var(--mark-from)" }} />
            <stop offset="1" style={{ stopColor: "var(--mark-to)" }} />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="8" fill={`url(#${fill})`} />
        <path d="M16 6.5 23.5 9.5v6c0 4.6-3.1 8.2-7.5 9.8-4.4-1.6-7.5-5.2-7.5-9.8v-6Z" fill="none" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
        <circle cx="16" cy="15.5" r="2.5" fill="var(--spark)" />
      </svg>
      <span>cyber<span className="ai">AI</span></span>
    </>
  );
}
