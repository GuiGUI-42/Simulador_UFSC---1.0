import React, { useState } from "react";

export default function HamburgerMenu({
  items = [],            // [{ label, href }]
  currentHref,           // ex.: "/discreto"
  iconColor = "#1976d2",
  drawerWidth = 260
}) {
  const [open, setOpen] = useState(false);

  const path = typeof currentHref === "string"
    ? currentHref
    : (typeof window !== "undefined" ? window.location?.pathname || "" : "");

  const list = Array.isArray(items) ? items : [];
  const visibleItems = list.filter(it => it && it.href && it.href !== path).slice(0, 4);

  return (
    <>
      <button
        aria-label="Abrir menu"
        onClick={() => setOpen(v => !v)}
        style={{
          position: "absolute",
          left: 12,
          width: 36,
          height: 36,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "transparent",
          border: "none",
          cursor: "pointer"
        }}
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
             stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            style={{
              position: "fixed",
              top: 0, left: 0, right: 0, bottom: 0,
              background: "rgba(0,0,0,0.25)",
              zIndex: 999
            }}
          />
          <div
            role="dialog"
            aria-label="Menu lateral"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              height: "100%",
              width: drawerWidth,
              background: "#fff",
              boxShadow: "2px 0 12px #0002",
              zIndex: 1000,
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <div style={{ fontWeight: "bold", color: iconColor }}>Menu</div>
              <button
                aria-label="Fechar menu"
                onClick={() => setOpen(false)}
                style={{ background: "transparent", border: "none", cursor: "pointer" }}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                     stroke="#555" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {visibleItems.map((it, idx) => (
                <li key={it.href || idx}>
                  <a
                    href={it.href}
                    onClick={() => setOpen(false)}
                    style={{ display: "block", padding: "8px 0", color: "#333", textDecoration: "none" }}
                  >
                    {it.label ?? it.href}
                  </a>
                </li>
              ))}
              {visibleItems.length === 0 && (
                <li style={{ color: "#777", paddingTop: 8 }}>Nada para exibir</li>
              )}
            </ul>
          </div>
        </>
      )}
    </>
  );
}