// A person in a table: their name, with the username under it. Students have no name on the
// platform (the server gives them their username as their name), so theirs is shown once.
export default function Person({ name, username }: { name: string; username: string }) {
  return (
    <span className="person">
      <strong>{name}</strong>
      {name !== username && <span className="muted">{username}</span>}
    </span>
  );
}
