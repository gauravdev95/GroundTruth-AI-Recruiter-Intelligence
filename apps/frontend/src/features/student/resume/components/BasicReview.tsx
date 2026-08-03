import { Input, Select } from "@/components";

import {
  BRANCH_OPTIONS,
  DEGREE_OPTIONS,
  TARGET_ROLE_OPTIONS,
  graduationYearOptions,
} from "../../constants";
import { FieldToggle } from "./FieldToggle";

const YEAR_OPTIONS = graduationYearOptions();

export interface BasicFieldState {
  included: boolean;
  value: string;
  fromResume: boolean;
}

export type BasicFieldName =
  | "headline"
  | "college"
  | "degree"
  | "branch"
  | "graduation_year"
  | "location"
  | "target_role";

export type BasicFieldsState = Record<BasicFieldName, BasicFieldState>;

interface BasicReviewProps {
  fields: BasicFieldsState;
  errors: Partial<Record<BasicFieldName, string>>;
  onChange: (name: BasicFieldName, next: Partial<BasicFieldState>) => void;
}

const LABELS: Record<BasicFieldName, string> = {
  headline: "Headline",
  college: "College",
  degree: "Degree",
  branch: "Branch",
  graduation_year: "Graduation year",
  location: "Location",
  target_role: "Target role",
};

/**
 * Section 1 review.
 *
 * Every field here is required by the section, but a resume supplies only some
 * of them — a target role in particular is forward-looking and appears on no
 * resume. Rather than hide that, each field states where its value came from
 * and the section refuses to submit until the required ones are filled.
 */
export function BasicReview({ fields, errors, onChange }: BasicReviewProps) {
  const renderSelect = (name: BasicFieldName, options: { value: string; label: string }[]) => (
    <FieldToggle
      key={name}
      label={LABELS[name]}
      included={fields[name].included}
      fromResume={fields[name].fromResume}
      onToggle={(included) => onChange(name, { included })}
      error={errors[name]}
      requiredHint={
        !fields[name].fromResume ? "Not on your resume — pick a value to include it." : undefined
      }
    >
      <Select
        options={options}
        placeholder="Select an option"
        value={fields[name].value}
        onChange={(event) => onChange(name, { value: event.target.value })}
      />
    </FieldToggle>
  );

  const renderInput = (name: BasicFieldName, placeholder: string) => (
    <FieldToggle
      key={name}
      label={LABELS[name]}
      included={fields[name].included}
      fromResume={fields[name].fromResume}
      onToggle={(included) => onChange(name, { included })}
      error={errors[name]}
    >
      <Input
        placeholder={placeholder}
        value={fields[name].value}
        onChange={(event) => onChange(name, { value: event.target.value })}
      />
    </FieldToggle>
  );

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="sm:col-span-2">
        {renderInput("headline", "Final-year CS student building compilers")}
      </div>
      {renderInput("college", "IIT Bombay")}
      {renderInput("location", "Mumbai, India")}
      {renderSelect("degree", DEGREE_OPTIONS)}
      {renderSelect("branch", BRANCH_OPTIONS)}
      {renderSelect("graduation_year", YEAR_OPTIONS)}
      {renderSelect("target_role", TARGET_ROLE_OPTIONS)}
    </div>
  );
}
