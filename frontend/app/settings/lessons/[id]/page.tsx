import LessonEditor from "@/components/LessonEditor";

export default async function LessonEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LessonEditor key={id} lessonId={id} />;
}
