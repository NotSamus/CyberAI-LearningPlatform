import Link from "next/link";
import { ChevronRight } from "lucide-react";

export type Crumb = { label: string; href?: string };

// The top of a page: where you are, the title with where it stands, one line about it, facts about
// it, its actions (one filled button at most: the main thing to do here), and tabs when the page has
// several views. Inside Teach and Admin the crumbs leave out the area itself: its tabs already say it.
// The title can also be the field it is typed in (the lesson editor): it is still the page's heading.
export default function PageHeader({ crumbs, title, status, description, meta, actions, tabs }: {
  crumbs?: Crumb[];
  title: React.ReactNode;
  status?: React.ReactNode;           // chips next to the title
  description?: React.ReactNode;
  meta?: React.ReactNode;             // facts in a line (.fact): who it is for, when it is due, how it is graded
  actions?: React.ReactNode;
  tabs?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="You are here">
          <ol className="crumbs">
            {crumbs.map((crumb, n) => (
              <li key={`${crumb.label}-${n}`} className="fact">
                {n > 0 && <ChevronRight aria-hidden />}
                {crumb.href ? <Link href={crumb.href}>{crumb.label}</Link> : <span>{crumb.label}</span>}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="title-row">
        <div className="title-main">
          <h1>{title}</h1>
          {status}
        </div>
        {actions && <div className="actions">{actions}</div>}
      </div>
      {description && <p className="description">{description}</p>}
      {meta && <p className="meta">{meta}</p>}
      {tabs}
    </header>
  );
}
