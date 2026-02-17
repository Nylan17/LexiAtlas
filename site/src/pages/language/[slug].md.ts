import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

function fmtYear(y: number) {
  const abs = Math.abs(Math.trunc(y));
  if (y < 0) return `${abs} BCE`;
  return `${abs} CE`;
}

function fmtPeriod(period: any): string {
  if (!period) return "";
  if (period.label) return String(period.label);
  const s = typeof period.start === "number" ? fmtYear(period.start) : "";
  const e = typeof period.end === "number" ? fmtYear(period.end) : "";
  if (s && e) return `${s} → ${e}`;
  return s || e || "";
}

export async function getStaticPaths() {
  const entries = await getCollection("languages");
  return entries.map((entry) => ({
    params: { slug: entry.slug }
  }));
}

export const GET: APIRoute = async ({ params }) => {
  const slug = params.slug;
  const entries = await getCollection("languages");
  const entry = entries.find((e) => e.slug === slug);
  if (!entry) {
    return new Response("Not found", { status: 404 });
  }

  const title = entry.data.title;
  const blurb = entry.data.blurb ? `${entry.data.blurb}\n\n` : "";
  const family = entry.data.family ? `- Family: ${entry.data.family}\n` : "";
  const branch = entry.data.branch ? `- Branch: ${entry.data.branch}\n` : "";
  const region = entry.data.region
    ? `- Region: ${Array.isArray(entry.data.region) ? entry.data.region.join("; ") : entry.data.region}\n`
    : "";
  const period = fmtPeriod(entry.data.period);
  const periodLine = period ? `- Period: ${period}\n` : "";

  const metaBlock = family || branch || region || periodLine ? `## At a glance\n\n${family}${branch}${region}${periodLine}\n` : "";

  // `body` contains the raw Markdown content (no frontmatter).
  const body = (entry as any).body ? String((entry as any).body).trim() : "";
  const content = `# ${title}\n\n${blurb}${metaBlock}${body}\n`;

  return new Response(content, {
    status: 200,
    headers: {
      "content-type": "text/markdown; charset=utf-8",
      "content-disposition": `attachment; filename="${encodeURIComponent(slug || "language")}.md"`
    }
  });
};

