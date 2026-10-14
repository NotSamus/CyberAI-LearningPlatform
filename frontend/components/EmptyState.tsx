import type { LucideIcon } from "lucide-react";

// What a page or list shows while there is nothing in it: what will be here, and how to start.
export default function EmptyState({ icon: Icon, title, children, action }: {
  icon: LucideIcon;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon"><Icon aria-hidden /></span>
      <h2>{title}</h2>
      {children && <p className="muted">{children}</p>}
      {action && <div className="row">{action}</div>}
    </div>
  );
}
