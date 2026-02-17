export type WhatsNewItem = {
  date?: string;
  text: string;
  href?: string;
};

// Keep this short (3–5 items). It’s meant to be edited by contributors.
export const WHATS_NEW: WhatsNewItem[] = [
  {
    text: "New: Bungo (Classical Japanese) resources page",
    href: "/language/%E6%96%87%E8%AA%9E-bungo-classical-japanese/"
  }
];

