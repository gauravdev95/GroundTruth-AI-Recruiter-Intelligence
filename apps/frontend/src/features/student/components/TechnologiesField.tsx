import { useEffect, useState } from "react";

import { Input } from "@/components";

interface TechnologiesFieldProps {
  label?: string;
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
  placeholder?: string;
}

/**
 * Comma-separated entry backed by a `string[]`.
 *
 * The raw text is local state rather than derived from `value` on every
 * keystroke: splitting on each change would eat the comma the moment it is
 * typed, so "React," could never become "React, Redux". The array is
 * published on change, and the text re-syncs only when the field's value is
 * replaced from outside (a reset after save, or switching sections).
 */
export function TechnologiesField({
  label = "Technologies",
  value,
  onChange,
  error,
  placeholder = "React, PostgreSQL, Docker",
}: TechnologiesFieldProps) {
  const [text, setText] = useState(() => value.join(", "));

  useEffect(() => {
    setText((current) => {
      const currentAsArray = current
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const isEquivalent =
        currentAsArray.length === value.length &&
        currentAsArray.every((item, index) => item === value[index]);
      return isEquivalent ? current : value.join(", ");
    });
  }, [value]);

  return (
    <Input
      label={label}
      placeholder={placeholder}
      value={text}
      error={error}
      onChange={(event) => {
        const next = event.target.value;
        setText(next);
        onChange(
          next
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        );
      }}
    />
  );
}
