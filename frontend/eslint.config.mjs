// The frontend's lint (npm run lint; next build runs it too): Next.js's own rules for React, hooks,
// accessibility basics and TypeScript, in ESLint's flat config through the compatibility layer.
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

const config = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
