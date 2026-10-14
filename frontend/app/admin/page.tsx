import { redirect } from "next/navigation";

// /admin itself has nothing to show: its first section is Accounts.
export default function AdminIndex() {
  redirect("/admin/accounts");
}
