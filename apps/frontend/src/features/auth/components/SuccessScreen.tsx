import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

interface SuccessScreenProps {
  title: string;
  description?: string;
  children?: ReactNode;
}

export function SuccessScreen({ title, description, children }: SuccessScreenProps) {
  return (
    <div className="flex flex-col items-center gap-4 py-2 text-center animate-fade-in">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 animate-scale-in">
        <CheckCircle2 size={30} strokeWidth={1.75} />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {description ? <p className="mt-1.5 text-sm text-slate-500">{description}</p> : null}
      </div>
      {children}
    </div>
  );
}
