import OpenNotebook from "@/components/OpenNotebook";

export default async function AssignmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OpenNotebook assignmentId={id} />;
}
