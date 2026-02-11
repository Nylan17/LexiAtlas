export const SITE = {
  // Set these in Cloudflare Pages env vars (Astro exposes PUBLIC_* at build time).
  // Example:
  //   PUBLIC_ISSUES_NEW_URL=https://github.com/OWNER/REPO/issues/new
  issuesNewUrl:
    import.meta.env.PUBLIC_ISSUES_NEW_URL ||
    "https://github.com/<owner>/<repo>/issues/new",
  issuesUrl:
    import.meta.env.PUBLIC_ISSUES_URL || "https://github.com/<owner>/<repo>/issues"
};

