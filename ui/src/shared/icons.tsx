import React from 'react';

const S = (p: { children: React.ReactNode; size?: number }) => (
  <svg width={p.size ?? 18} height={p.size ?? 18} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{p.children}</svg>
);

export const Icon: Record<string, (p?: { size?: number }) => React.ReactElement> = {
  shield: (p) => <S size={p?.size}><path d="M12 3l8 3v5c0 4.5-3 8-8 10-5-2-8-5.5-8-10V6z" /></S>,
  home: (p) => <S size={p?.size}><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></S>,
  route: (p) => <S size={p?.size}><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="6" r="2.5" /><path d="M8 18h6a4 4 0 0 0 4-4V9" /></S>,
  bell: (p) => <S size={p?.size}><path d="M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" /><path d="M10 20a2 2 0 0 0 4 0" /></S>,
  grid: (p) => <S size={p?.size}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></S>,
  box: (p) => <S size={p?.size}><path d="M21 8l-9-5-9 5 9 5 9-5Z" /><path d="M3 8v8l9 5 9-5V8" /><path d="M12 13v8" /></S>,
  server: (p) => <S size={p?.size}><rect x="3" y="4" width="18" height="7" rx="2" /><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 7.5h.01M7 16.5h.01" /></S>,
  policy: (p) => <S size={p?.size}><path d="M12 3l7 3v6c0 4-3 7-7 8-4-1-7-4-7-8V6z" /><path d="M9 12l2 2 4-4" /></S>,
  events: (p) => <S size={p?.size}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></S>,
  logs: (p) => <S size={p?.size}><path d="M5 3h11l3 3v15H5z" /><path d="M8 9h8M8 13h8M8 17h5" /></S>,
  cog: (p) => <S size={p?.size}><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></S>,
  providers: (p) => <S size={p?.size}><path d="M12 3a9 9 0 1 0 9 9" /><path d="M12 3v9l6 4" /></S>,
  adapters: (p) => <S size={p?.size}><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" /></S>,
  skills: (p) => <S size={p?.size}><path d="M12 3l2.5 5 5.5.8-4 3.9 1 5.5L12 16l-5 2.6 1-5.5-4-3.9 5.5-.8z" /></S>,
  queue: (p) => <S size={p?.size}><rect x="3" y="4" width="18" height="4" rx="1.5" /><rect x="3" y="10" width="18" height="4" rx="1.5" /><rect x="3" y="16" width="12" height="4" rx="1.5" /></S>,
  audit: (p) => <S size={p?.size}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h4" /></S>,
  bolt: (p) => <S size={p?.size}><path d="M13 2 4 14h7l-2 8 9-12h-7z" /></S>,
  help: (p) => <S size={p?.size}><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 0 1 4 2c0 1.5-2 2-2 3" /><path d="M12 17h.01" /></S>,
  sun: (p) => <S size={p?.size}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></S>,
  moon: (p) => <S size={p?.size}><path d="M21 12.8A8 8 0 1 1 11.2 3a6 6 0 0 0 9.8 9.8Z" /></S>,
  chevron: (p) => <S size={p?.size}><path d="M6 9l6 6 6-6" /></S>,
};
