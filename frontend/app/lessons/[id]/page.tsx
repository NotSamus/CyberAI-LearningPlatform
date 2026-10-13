import LessonReader from "@/components/LessonReader";

export default async function LessonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LessonReader key={id} lessonId={id} />;
}
