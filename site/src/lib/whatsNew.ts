export type WhatsNewItem = {
  date?: string;
  text: string;
  href?: string;
};

// Keep this short (3–5 items). It’s meant to be edited by contributors.
export const WHATS_NEW: WhatsNewItem[] = [
  {
    text: "New: Pali resources page",
    href: "/language/%E0%A4%AA%E0%A4%BE%E0%A4%B2%E0%A5%80-pali/"
  },
  {
    text: "New: Classical Japanese (Bungo) resources page",
    href: "/language/%E6%96%87%E8%AA%9E-bungo-classical-japanese/"
  }
];

