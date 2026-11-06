// A lesson's tags as small chips, each with a coloured dot. The colour comes from the tag's name, so
// a tag looks the same everywhere. It only decorates: the word says what the tag is.
const HUES: Record<string, number> = { cybersecurity: 205, ai: 275 };     // the two suggested tags: blue and purple

export function tagStyle(tag: string): React.CSSProperties {
  const key = tag.toLowerCase();
  let hue = HUES[key];
  if (hue === undefined) {
    hue = 0;
    for (const letter of key) hue = (hue * 31 + letter.charCodeAt(0)) % 360;
  }
  return { "--tag-hue": hue } as React.CSSProperties;
}

export default function TagChips({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <span className="tags" aria-label="Tags">
      {tags.map((tag) => <span key={tag} className="tag" style={tagStyle(tag)}>{tag}</span>)}
    </span>
  );
}
