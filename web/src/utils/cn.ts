// Tiny class-name composition helper, inspired by `clsx`. Kept dependency-free
// because clsx + tailwind-merge would pull in machinery for a Tailwind setup
// we don't use — and the bundle-size delta on the main chunk is not nothing.
//
// Behaviour:
//   cn('a', 'b')                     -> 'a b'
//   cn('a', false && 'b', 'c')       -> 'a c'
//   cn('a', { b: true, c: false })   -> 'a b'
//   cn(['a', null, 'b'])             -> 'a b'
//   cn('a', undefined, '', 'b')      -> 'a b'  (empties / nullish skipped)
//
// Conventions:
//   - Pass falsy values freely; they're filtered out.
//   - Use object form for conditional toggles when readability beats inline
//     ternaries.
//   - The result is collapsed-whitespace so callers can interpolate freely.

type ClassValue =
  | string
  | number
  | null
  | undefined
  | false
  | true
  | ClassDict
  | ClassValue[];

interface ClassDict {
  [key: string]: unknown;
}

function append(parts: string[], value: ClassValue): void {
  if (!value && value !== 0) return;
  if (typeof value === 'string' || typeof value === 'number') {
    parts.push(String(value));
    return;
  }
  if (Array.isArray(value)) {
    for (const inner of value) append(parts, inner);
    return;
  }
  if (typeof value === 'object') {
    for (const key of Object.keys(value)) {
      if ((value as ClassDict)[key]) parts.push(key);
    }
  }
}

export function cn(...inputs: ClassValue[]): string {
  const parts: string[] = [];
  for (const value of inputs) append(parts, value);
  return parts.join(' ').replace(/\s+/g, ' ').trim();
}

export default cn;
