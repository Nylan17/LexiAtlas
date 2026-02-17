import { defineCollection, z } from "astro:content";

const languages = defineCollection({
  type: "content",
  schema: z.object({
    title: z.string(),
    aka: z.array(z.string()).optional(),
    tags: z.array(z.string()).optional(),
    // Short “why study this language?” / quick-start text shown at top of the page.
    blurb: z.string().optional(),
    // Lightweight categorization for browsing.
    family: z.string().optional(),
    branch: z.string().optional(),
    region: z.union([z.string(), z.array(z.string())]).optional(),
    // Coarse region used for browsing facets (e.g., "Europe", "Middle East").
    regionGroup: z.union([z.string(), z.array(z.string())]).optional(),
    // Approximate period of use/activity. Use negative years for BCE (e.g., -1200).
    period: z
      .object({
        start: z.number().optional(),
        end: z.number().optional(),
        label: z.string().optional()
      })
      .optional(),
    // Approximate modern-reference geography (avoid false precision).
    // - Prefer center+radiusKm for fuzzy regions
    // - Use bbox [westLon, southLat, eastLon, northLat] for wide spreads
    geo: z
      .object({
        center: z
          .object({
            lat: z.number(),
            lon: z.number()
          })
          .optional(),
        radiusKm: z.number().optional(),
        bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]).optional(),
        note: z.string().optional()
      })
      .optional(),
    typing: z
      .object({
        note: z.string().optional(),
        // External links to IMEs, fonts, and input help.
        links: z
          .array(
            z.object({
              label: z.string(),
              url: z.string()
            })
          )
          .optional(),
        // Copy/paste palette (characters or short strings).
        palette: z.array(z.string()).optional()
      })
      .optional(),
    source: z.string().optional(),
    attribution: z.string().optional()
  })
});

export const collections = { languages };

