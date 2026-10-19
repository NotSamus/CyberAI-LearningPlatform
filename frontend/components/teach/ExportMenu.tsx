"use client";
import { ChevronDown, Download, FileSpreadsheet, FileText } from "lucide-react";
import Menu from "@/components/Menu";

// "Export" with a choice of Excel or CSV: each student's lessons, knowledge checks, assignments and
// scores, as a file the server makes (api/app/exports.py). `path` is the file's address without its
// extension: /teach/students for every student, /teach/courses/<id>/students for one course.
export default function ExportMenu({ path, label }: { path: string; label: string }) {
  return (
    <Menu
      label={label} triggerClass="secondary"
      trigger={<><Download aria-hidden />Export<ChevronDown aria-hidden /></>}
      items={[
        { label: "Excel (.xlsx)", icon: FileSpreadsheet, href: `/api${path}.xlsx`, download: true },
        { label: "CSV (.csv)", icon: FileText, href: `/api${path}.csv`, download: true },
      ]}
    />
  );
}
