import React from "react";

export default function Home() {
  return (
    <div style={{ maxWidth: 720, margin: "40px auto", textAlign: "center" }}>
      <h1>Simulador</h1>
      <p>Escolha um módulo:</p>
      <div style={{ display: "flex", gap: 16, justifyContent: "center", marginTop: 16 }}>
        <a
          href="#/discreto"
          style={{ padding: "10px 16px", borderRadius: 6, background: "#1976d2", color: "#fff", textDecoration: "none" }}
        >
          Resposta Discreta
        </a>
        <a
          href="#/blocos"
          style={{ padding: "10px 16px", borderRadius: 6, background: "#ff9800", color: "#fff", textDecoration: "none" }}
        >
          Editor de Blocos
        </a>
      </div>
    </div>
  );
}