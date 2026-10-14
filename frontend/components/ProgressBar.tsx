// How much of something is done, as a thin bar with the numbers in words beside it: the words
// carry the value, the bar only helps to see it at a glance.
export default function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  const share = max > 0 ? Math.min(100, Math.round((100 * value) / max)) : 0;
  return (
    <span className={`progress ${max > 0 && value >= max ? "done" : ""}`}>
      <span className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
        <span className="progress-fill" style={{ width: `${share}%` }} />
      </span>
      <span>{label}</span>
    </span>
  );
}
