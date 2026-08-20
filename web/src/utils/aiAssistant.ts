// Pure (JSX-free, i18n-free) helpers for the AI assistant drawer:
//   - filterSkills: slash-command autocomplete matching for /skill commands
//   - clampDrawerWidth: keeps the resizable drawer inside sane bounds
// Kept separate from AIWorkflowModal so they are unit-testable in isolation.

export interface SkillSummary {
  name: string;
  description?: string;
  source?: string;
}

export const SKILL_SUGGESTION_LIMIT = 8;

/**
 * Match skills for a slash-command query (the text after the leading '/').
 * Case-insensitive: prefix match on the skill name, or substring match on its
 * description. Name-prefix matches rank above description-only matches; order
 * within each group is stable (the engine returns skills sorted by name).
 */
export function filterSkills(
  query: string,
  skills: readonly SkillSummary[],
  limit: number = SKILL_SUGGESTION_LIMIT,
): SkillSummary[] {
  const q = query.trim().toLowerCase();
  if (!q) return skills.slice(0, limit);
  const nameMatches: SkillSummary[] = [];
  const descriptionMatches: SkillSummary[] = [];
  for (const skill of skills) {
    if (skill.name.toLowerCase().startsWith(q)) {
      nameMatches.push(skill);
    } else if ((skill.description || '').toLowerCase().includes(q)) {
      descriptionMatches.push(skill);
    }
  }
  return [...nameMatches, ...descriptionMatches].slice(0, limit);
}

export const AI_DRAWER_MIN_WIDTH = 320;
export const AI_DRAWER_DEFAULT_WIDTH = 380;
export const AI_DRAWER_MAX_VW_RATIO = 0.8;

/**
 * Clamp a drawer width (px) into [AI_DRAWER_MIN_WIDTH, 80% of the viewport].
 * Non-finite input falls back to the default width. When the viewport is so
 * narrow that 80% of it is below the minimum, the minimum wins.
 */
export function clampDrawerWidth(widthPx: number, viewportWidthPx: number): number {
  if (!Number.isFinite(widthPx)) return AI_DRAWER_DEFAULT_WIDTH;
  const max = Math.max(AI_DRAWER_MIN_WIDTH, Math.floor(viewportWidthPx * AI_DRAWER_MAX_VW_RATIO));
  return Math.min(Math.max(Math.round(widthPx), AI_DRAWER_MIN_WIDTH), max);
}
