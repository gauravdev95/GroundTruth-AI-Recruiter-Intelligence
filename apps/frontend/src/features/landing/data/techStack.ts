import { Cpu, Database, FileCode2, Github, GitBranch } from "lucide-react";

import type { TechBadge } from "../types";

/** Technologies listed in the "Built on" section. */
export const TECH_STACK: TechBadge[] = [
  { t: "Next.js", I: FileCode2 },
  { t: "FastAPI", I: Cpu },
  { t: "PostgreSQL + pgvector", I: Database },
  { t: "Tree-sitter / AST", I: GitBranch },
  { t: "GitHub OAuth", I: Github },
];
