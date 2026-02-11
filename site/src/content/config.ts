import { defineCollection, z } from "astro:content";

const languages = defineCollection({
  type: "content",
  schema: z.object({
    title: z.string(),
    aka: z.array(z.string()).optional(),
    tags: z.array(z.string()).optional(),
    source: z.string().optional(),
    attribution: z.string().optional()
  })
});

export const collections = { languages };

