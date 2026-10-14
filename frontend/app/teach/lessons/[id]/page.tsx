import LessonEditor from "@/components/LessonEditor";

// The editor shows the lesson's header itself, with its Write and Progress tabs: its title is typed there.
export default async function LessonEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LessonEditor key={id} lessonId={id} />;
}
