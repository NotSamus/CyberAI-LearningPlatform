"use client";
import { ChartColumn, PencilLine } from "lucide-react";
import Tabs from "@/components/Tabs";

// The views of one lesson: writing it, and how its students are doing. A client component, so that
// a server page can show it: the icons cannot be sent from the server to Tabs.
export default function LessonTabs({ id }: { id: string | number }) {
  return (
    <Tabs
      kind="item" label="Views of this lesson"
      tabs={[
        { href: `/teach/lessons/${id}`, label: "Write", icon: PencilLine, exact: true },
        { href: `/teach/lessons/${id}/progress`, label: "Progress", icon: ChartColumn },
      ]}
    />
  );
}
