import React, { useEffect, useMemo, useState, useRef } from "react";
import Plot from "react-plotly.js";
import "./blocos.css";

// Dimensões por tipo de bloco (default e soma)
const BLOCO_DIMS = {
  default: { width: 10, height: 50 },
  soma:    { width: 80, height: 70 } // largura menor, altura maior
};
function getBlocoDims(bloco) {
  // FT: base 150; +50 por coeficiente acima de 2 (usa o maior entre num e den)
  if (bloco?.tipo === "ft") {
    const numLen = Array.isArray(bloco?.num) ? bloco.num.length : 0;
    const denLen = Array.isArray(bloco?.den) ? bloco.den.length : 0;
    const maxLen = Math.max(numLen, denLen);
    const extra = Math.max(0, maxLen - 2);
    return { width: 160 + extra * 50, height: BLOCO_DIMS.default.height };
  }

  // Somador: mantém padrão para 1–2 entradas; com 3 entradas altura = 90
  if (bloco?.tipo === "soma") {
    const n = Math.min(3, Math.max(1, bloco?.nEntradas ?? 2));
    const h = n >= 3 ? 90 : BLOCO_DIMS.soma.height;
    return { width: BLOCO_DIMS.soma.width, height: h };
  }

  return BLOCO_DIMS.default;
}

// Menu idêntico ao das páginas HTML (pagina2.html)
function MenuHtmlLike() {
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("dark-mode") === "true");
  const menuRef = useRef(null);
  const closeTimer = useRef(null);

  useEffect(() => {
    const onDocClick = (e) => {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  useEffect(() => {
    document.body.classList.toggle("dark-mode", dark);
    localStorage.setItem("dark-mode", String(dark));
  }, [dark]);

  const openMenu = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    setOpen(true);
  };
  const delayedClose = () => {
    closeTimer.current = setTimeout(() => setOpen(false), 300);
  };

  return (
    <div
      className={"menu" + (open ? " open" : "")}
      ref={menuRef}
      style={{ position: "fixed", top: 8, left: 8, zIndex: 1000 }}
      onMouseEnter={openMenu}
      onMouseLeave={delayedClose}
    >
      <button
        id="menu-toggle-btn"
        style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div className="menu-icon" />
          <div className="menu-icon" />
          <div className="menu-icon" />
        </div>
      </button>

      <div className="menu-content">
        <label>
          <input
            id="dark-mode-toggle"
            type="checkbox"
            checked={dark}
            onChange={e => setDark(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          <span id="dark-mode-icon">{dark ? "🌞" : "🌙"}</span>
        </label>

        <a href="/principal" className="menu-link" style={{ marginTop: 16 }}>Página Inicial</a>

        <div style={{ marginTop: 16, marginBottom: 2, fontWeight: "bold", color: "#1976d2" }}>Sinais e Sistemas</div>
        <a href="/sinais" className="menu-link" style={{ marginTop: 0 }}>Resposta do Sistema</a>

        <div style={{ marginTop: 16, marginBottom: 2, fontWeight: "bold", color: "#1976d2" }}>Controle</div>
        <a href="/alocacao" className="menu-link" style={{ marginTop: 0 }}>Alocação de Polos</a>
        <a href="/raizes" className="menu-link" style={{ marginTop: 0 }}>Lugar das Raízes</a>
        <a href="/simuladorcomp" className="menu-link" style={{ marginTop: 0 }}>Simulador Completo</a>
      </div>
    </div>
  );
}

// Helpers de polinômio e FT
function latexPoly(coeffs, varName = "s") {
  if (!coeffs?.length) return "0";
  const ordem = coeffs.length - 1;
  return coeffs.map((c, i) => {
    if (c === 0) return null;
    const pot = ordem - i;
    const cstr = (c === 1 && pot !== 0) ? "" : (c === -1 && pot !== 0) ? "-" : String(c);
    if (pot > 1) return `${cstr}${varName}^${pot}`;
    if (pot === 1) return `${cstr}${varName}`;
    return `${cstr}`;
  }).filter(Boolean).join(" + ").replace(/\+\s-\s/g, "- ");
}
function polyMul(a, b) {
  const res = Array(a.length + b.length - 1).fill(0);
  for (let i = 0; i < a.length; ++i)
    for (let j = 0; j < b.length; ++j)
      res[i + j] += a[i] * b[j];
  return res;
}
function polyAdd(a, b) {
  const n = Math.max(a.length, b.length);
  const res = [];
  for (let i = 0; i < n; ++i) {
    const ai = a[a.length - n + i] || 0;
    const bi = b[b.length - n + i] || 0;
    res.push(ai + bi);
  }
  while (res.length > 1 && Math.abs(res[0]) < 1e-12) res.shift();
  return res;
}
function multiplyTF(num1, den1, num2, den2) {
  return { num: polyMul(num1, num2), den: polyMul(den1, den2) };
}
function sumTFs(tfList) {
  if (!tfList?.length) return { num: [0], den: [1] };
  let acc = tfList[0];
  for (let i = 1; i < tfList.length; ++i) {
    const a = acc, b = tfList[i];
    const num = polyAdd(polyMul(a.num, b.den), polyMul(b.num, a.den));
    const den = polyMul(a.den, b.den);
    acc = { num, den };
  }
  return acc;
}

// Novo: polinômio “bonito” com 2 casas (ex.: s - 0.00, 2.00s^2 + 1.50s + 3.00)
function prettyPoly(coeffs, varName = "s", decimals = 2) {
  if (!coeffs?.length) return (0).toFixed(decimals);
  const ordem = coeffs.length - 1;
  const parts = [];
  for (let i = 0; i < coeffs.length; i++) {
    const c = coeffs[i];
    const pot = ordem - i;
    if (Math.abs(c) < 1e-12) continue;
    const sign = c >= 0 ? "+" : "-";
    const abs = Math.abs(c);
    const coeffStr = (abs === 1 && pot !== 0) ? "" : abs.toFixed(decimals);
    let term = "";
    if (pot > 1) term = `${coeffStr ? coeffStr : ""}${coeffStr ? "" : ""}${varName}^${pot}`;
    else if (pot === 1) term = `${coeffStr ? coeffStr : ""}${coeffStr ? "" : ""}${varName}`;
    else term = `${abs.toFixed(decimals)}`;
    parts.push({ sign, term });
  }
  if (!parts.length) return (0).toFixed(decimals);
  let out = (parts[0].sign === "-" ? "-" : "") + parts[0].term;
  for (let i = 1; i < parts.length; i++) out += ` ${parts[i].sign} ${parts[i].term}`;
  return out.replace(/\s\+\s-/g, " - ");
}

// Componentes UI
function Bloco({ bloco, onClick, onDragStart, dragging, onInputDotDown, onOutputDotDown, isInputActive, isOutputActive, deleteMode, onDelete }) {
  // Limite máx 3 entradas
  const somaEntradas = Math.min(3, Math.max(1, bloco?.nEntradas ?? (bloco.tipo === "soma" ? 2 : 1)));
  const dims = getBlocoDims(bloco);

  return (
    <div
      className={"bloco" + (bloco.tipo === "soma" ? " bloco-soma" : "") + (dragging ? " dragging" : "")}
      style={{ left: bloco.x, top: bloco.y, zIndex: dragging ? 10 : 1, position: "absolute", width: dims.width, height: dims.height }}
      onMouseDown={e => {
        if (deleteMode) {
          e.preventDefault();
          e.stopPropagation();
          onDelete(bloco.id);
          return;
        }
        onDragStart(e, bloco.id);
      }}
    >
      <button
        className="edit-btn"
        title={deleteMode ? "Remover bloco" : "Editar bloco"}
        onMouseDown={e => e.stopPropagation()}
        onClick={e => {
          e.stopPropagation();
          if (deleteMode) { onDelete(bloco.id); return; }
          onClick();
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z" fill="currentColor"/>
          <path d="M20.71 7.04a1.003 1.003 0 0 0 0-1.42l-2.34-2.34a1.003 1.003 0 0 0-1.42 0l-1.83 1.83 3.75 3.75 1.84-1.82z" fill="currentColor"/>
        </svg>
      </button>

      {/* Entradas: múltiplos pontos quando "soma" */}
      {bloco.tipo === "soma"
        ? Array.from({ length: somaEntradas }).map((_, i) => {
            const topPct = ((i + 1) / (somaEntradas + 1)) * 100;
            const sign = (Array.isArray(bloco.signs) && Number(bloco.signs[i]) === -1) ? "-" : "+";
            return (
              <div
                key={`in-${i}`}
                className={"io-dot input sum-input-dot" + (isInputActive ? " active" : "")}
                title={`Entrada ${i + 1} (${sign})`}
                style={{ top: `${topPct}%` }}
                onMouseDown={e => { e.stopPropagation(); onInputDotDown(bloco.id, e); }}
                aria-label={`Entrada ${i + 1} (${sign})`}
              >
                <span className="io-sign">{sign}</span>
              </div>
            );
          })
        : (
          <div
            className={"io-dot input" + (isInputActive ? " active" : "")}
            title="Entrada"
            onMouseDown={e => { e.stopPropagation(); onInputDotDown(bloco.id, e); }}
          />
        )
      }

      <div
        className={"io-dot output" + (isOutputActive ? " active" : "")}
        title="Saída"
        onMouseDown={e => { e.stopPropagation(); onOutputDotDown(bloco.id, e); }}
      />

      {/* Conteúdo do bloco */}
      <div className="bloco-content">
        {bloco.tipo === "ft" ? (
          <div className="ft-display">
            <i>G(s)</i>
            <span>&nbsp;=&nbsp;</span>
            <span className="frac" aria-label="G(s) em fração">
              <span className="num">( {prettyPoly(bloco.num)} )</span>
              <span className="bar"></span>
              <span className="den">( {prettyPoly(bloco.den)} )</span>
            </span>
          </div>
        ) : bloco.tipo === "soma" ? (
          <div className="sum-symbol" aria-label="Somador">Σ</div>
        ) : bloco.tipo === "step" ? (
          <div className="step-icon" aria-label="Sinal Degrau">
            <svg viewBox="0 0 100 60" className="step-svg" role="img" aria-label="Curva de degrau">
              {/* eixos */}
              <line x1="5" y1="50" x2="95" y2="50" className="step-axis" />
              <line x1="5" y1="55" x2="5"  y2="5"  className="step-axis" />
              {/* degrau */}
              <path d="M5 50 L45 50 L45 15 L95 15" className="step-curve" />
            </svg>
          </div>
        ) : bloco.tipo === "constante" ? (
          <div className="const-value" aria-label="Valor constante">
            {Number.isFinite(+bloco.valor) ? bloco.valor : 1}
          </div>
        ) : (
          <>
            <div
              className="bloco-title"
              style={{ fontWeight: "bold", marginBottom: 8, cursor: "default" }}
              onClick={e => { e.stopPropagation(); }}
            >
              Bloco #{bloco.id}
            </div>
            <div style={{ fontFamily: "monospace", marginTop: 8, textAlign: "center" }}>
              {bloco.tipo === "ganho" ? (
                <span style={{ fontFamily: "serif" }}>Ganho: <b>{bloco.k ?? 1}</b></span>
              ) : bloco.tipo === "comparador" ? (
                <div style={{ fontFamily: "serif" }}>
                  <div>Comparador Σ (k·fb): <b>{bloco.k ?? -1}</b></div>
                  {(bloco?.den?.length ?? 0) > 1 && (
                    <div style={{ marginTop: 4 }}>
                      G(s) = (<span>{latexPoly(bloco.num)}</span>) / (<span>{latexPoly(bloco.den)}</span>)
                    </div>
                  )}
                </div>
              ) : (
                <>G(s) = <span style={{ fontFamily: "serif" }}>{`(${latexPoly(bloco.num)}) / (${latexPoly(bloco.den)})`}</span></>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ArcInspectModal({ left, top, fromBloco, toBloco, resultTF, onClose, accumulatedTF }) {
  const renderFT = (num, den) => `(${latexPoly(num)}) / (${latexPoly(den)})`;
  return (
    <div style={{
      position: "fixed", left: 0, top: 0, width: "100vw", height: "100vh",
      background: "rgba(0,0,0,0.08)", zIndex: 2000
    }} onClick={onClose}>
      <div style={{
        position: "absolute", left, top,
        background: "#fff", borderRadius: 10, boxShadow: "0 4px 24px #0003",
        padding: "18px 22px 14px 22px", minWidth: 320, maxWidth: 420, zIndex: 2100, border: "2px solid #2196f3"
      }} onClick={e => e.stopPropagation()}>
        <span style={{ position: "absolute", top: 8, right: 12, fontSize: "1.3em", color: "#888", cursor: "pointer" }} onClick={onClose}>&times;</span>
        <div style={{ fontWeight: "bold", marginBottom: 8, color: "#2196f3" }}>Interação entre blocos</div>
        <div style={{ fontFamily: "serif", fontSize: "1.1em", margin: "8px 0 0 0" }}>
          <div>
            <b>FT acumulada até este arco:</b><br />
            <span>G(s) = {renderFT(accumulatedTF.num, accumulatedTF.den)}</span>
          </div>
          <div style={{ marginTop: 12 }}>
            <b>Bloco origem:</b><br />
            <span>G(s) = {renderFT(fromBloco.num, fromBloco.den)}</span>
          </div>
          <div style={{ marginTop: 12 }}>
            <b>Bloco destino:</b><br />
            <span>G(s) = {renderFT(toBloco.num, toBloco.den)}</span>
          </div>
          <div style={{ marginTop: 12 }}>
            <b>Resultado após este arco:</b><br />
            <span>G(s) = {renderFT(resultTF.num, resultTF.den)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function SaidaGraphModal({ open, onClose, graph }) {
  const [plotData, setPlotData] = useState(null);

  useEffect(() => {
    if (!open || !graph) return;
    let cancelled = false;
    setPlotData(null);

    async function run() {
      const payload = {
        blocks: graph.blocos,
        links: graph.links,
        t_final: 40,
        dt: 0.01
      };
      const opts = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      };
      const tryFetch = async (url) => {
        const r = await fetch(url, opts);
        let data = null;
        try { data = await r.json(); } catch {}
        if (!r.ok) {
          const msg = data?.message ? `HTTP ${r.status}: ${data.message}` : `HTTP ${r.status}`;
          throw new Error(msg);
        }
        return data;
      };

      const proto = (window.location.protocol === 'https:') ? 'https' : 'http';
      const host = window.location.hostname || 'localhost';
      const candidates = [
        `${proto}://${host}:5000/simular_blocos`,
        `${proto}://localhost:5000/simular_blocos`,
        `${proto}://127.0.0.1:5000/simular_blocos`,
        `${proto}://[::1]:5000/simular_blocos`,
        "/simular_blocos", // deixa por último
      ];

      let ok = false, lastErr = null;
      for (const url of candidates) {
        try {
          const data = await tryFetch(url);
          if (!cancelled) { setPlotData(data); ok = true; }
          break;
        } catch (e) { lastErr = e; }
      }
      if (!ok && !cancelled) {
        setPlotData({ t: [], y: [], error: lastErr?.message || "Falha ao contatar o servidor (porta 5000)." });
      }
    }

    run();
    return () => { cancelled = true; };
  }, [open, graph]);

  if (!open) return null;

  const hasEntradaSaida = graph?.links?.some(l => l.to === "saida");

  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
        background: "rgba(0,0,0,0.18)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 4000
      }}
      onClick={onClose}
    >
      <div
        style={{ background: "#fff", borderRadius: 10, padding: 18, minWidth: 420, boxShadow: "0 4px 24px #0003", position: "relative" }}
        onClick={e => e.stopPropagation()}
      >
        <span style={{ position: "absolute", top: 8, right: 12, fontSize: "1.5em", cursor: "pointer", color: "#888" }} onClick={onClose}>&times;</span>
        <div style={{ fontWeight: "bold", marginBottom: 8, color: "#ff9800" }}>Saída do Processo</div>

        {!plotData && (
          <div style={{ width: 520, height: 320, display: "flex", alignItems: "center", justifyContent: "center", color: "#888" }}>
            Calculando resposta...
          </div>
        )}

        {plotData?.error && (
          <div style={{ width: 520, height: 320, display: "flex", alignItems: "center", justifyContent: "center", color: "#d32f2f" }}>
            {plotData.error}
          </div>
        )}

        {plotData && !plotData.error && (!hasEntradaSaida || (plotData.t?.length ?? 0) === 0) && (
          <div style={{ width: 520, height: 320, display: "flex", alignItems: "center", justifyContent: "center", color: "#888", textAlign: "center" }}>
            Conecte pelo menos um bloco à “Saída” e tente novamente.
          </div>
        )}

        {plotData && !plotData.error && (plotData.t?.length ?? 0) > 0 && (
          <Plot
            data={[{ x: plotData.t, y: plotData.y, mode: "lines", name: "Saída" }]}
            layout={{ width: 520, height: 320, title: "Resposta ao Degrau", xaxis: { title: "Tempo (s)" }, yaxis: { title: "Saída" }, margin: { t: 40 } }}
            config={{ displayModeBar: false }}
          />
        )}
      </div>
    </div>
  );
}

function SaidaBloco({ pos, onInputDotDown, isInputActive, onSaidaClick }) {
  return (
    <div
      style={{
        background: "#394053", border: "2px solid #4E4A59", borderRadius: "50%",
        width: 70, height: 70, position: "absolute", display: "flex",
        alignItems: "center", justifyContent: "center", left: pos.x, top: pos.y,
        boxShadow: "0 2px 8px #0001", fontWeight: "bold", fontSize: "1.2em", color: "#f99f17ff",
        zIndex: 5, cursor: "pointer", userSelect: "none"
      }}
      onClick={onSaidaClick}
      title="Clique para ver o gráfico da saída"
    >
      <div
        className={"io-dot input" + (isInputActive ? " active" : "")}
        title="Entrada"
        style={{ position: "absolute", top: "50%", left: "-10px", transform: "translateY(-50%)", background: "#ff9800" }}
        onMouseDown={e => { e.stopPropagation(); onInputDotDown("saida", e); }}
      />
      <span>➠<br />Saída</span>
    </div>
  );
}

function ConfigModal({ bloco, onClose, onSave }) {
  const [num, setNum] = useState((bloco.num || [1]).join(","));
  const [den, setDen] = useState((bloco.den || [1,1]).join(","));
  const [valor, setValor] = useState(bloco.valor ?? 1);
  const [k, setK] = useState(bloco.k ?? (bloco.tipo === "ganho" ? 1 : -1));
  const [amp, setAmp] = useState(bloco.amp ?? 1);
  const [t0, setT0] = useState(bloco.t0 ?? 0);
  const [nEntradas, setNEntradas] = useState(bloco.nEntradas ?? (bloco.tipo === "soma" ? 2 : 1));
  // Sinais do somador (+1 ou -1) – padrão +
  const [signs, setSigns] = useState(() => {
    const n = Math.min(3, Math.max(1, bloco.nEntradas ?? (bloco.tipo === "soma" ? 2 : 1)));
    const base = Array.isArray(bloco.signs) ? bloco.signs.slice(0, n).map(v => (Number(v) === -1 ? -1 : 1)) : [];
    while (base.length < n) base.push(1);
    return base;
  });

  const saveFT = () => {
    const numArr = String(num).split(",").map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
    const denArr = String(den).split(",").map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
    if (denArr.length === 0 || denArr.every(x => x === 0)) { alert("Denominador inválido!"); return; }
    onSave({ ...bloco, num: numArr, den: denArr });
    onClose();
  };
  const saveConst = () => {
    const v = parseFloat(valor);
    if (!Number.isFinite(v)) { alert("Valor inválido!"); return; }
    onSave({ ...bloco, valor: v });
    onClose();
  };
  const saveGain = () => {
    const kv = parseFloat(k);
    if (!Number.isFinite(kv)) { alert("Ganho inválido!"); return; }
    onSave({ ...bloco, k: kv });
    onClose();
  };
// Novo: salvar Somador (n entradas até 3 e sinais +/-)
  const saveSum = () => {
    let n = parseInt(nEntradas, 10);
    if (!Number.isFinite(n)) n = 2;
    n = Math.min(3, Math.max(1, n));
    const s = (Array.from({ length: n }).map((_, i) => (Number(signs[i]) === -1 ? -1 : 1)));
    onSave({ ...bloco, nEntradas: n, signs: s });
    onClose();
  };

  const saveStep = () => {
    const A = parseFloat(amp);
    const t = parseFloat(t0);
    if (!Number.isFinite(A) || !Number.isFinite(t)) { alert("Parâmetros inválidos!"); return; }
    onSave({ ...bloco, amp: A, t0: t });
    onClose();
  };
  const saveComparator = () => {
    const kv = parseFloat(k);
    if (!Number.isFinite(kv)) { alert("Ganho inválido!"); return; }
    const numArr = String(num).split(",").map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
    const denArr = String(den).split(",").map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
    if (denArr.length === 0 || denArr.every(x => x === 0)) { alert("Denominador inválido!"); return; }
    onSave({ ...bloco, k: kv, num: numArr, den: denArr });
    onClose();
  };

  return (
    <div
      style={{ position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", background: "rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 3000 }}
      onClick={onClose}
    >
      <div
        style={{ background: "#fff", borderRadius: 8, padding: 24, minWidth: 320, boxShadow: "0 2px 16px #0003", position: "relative" }}
        onClick={e => e.stopPropagation()}
      >
        <span style={{ position: "absolute", top: 8, right: 12, fontSize: "1.5em", cursor: "pointer", color: "#888" }} onClick={onClose}>&times;</span>
        <h3>Configurar Bloco #{bloco.id}</h3>

        {bloco.tipo === "step" ? (
          <>
            <label>Amplitude A:<br />
              <input value={amp} onChange={e => setAmp(e.target.value)} style={{ width: "100%" }} />
            </label>
            <div style={{ marginTop: 12 }}>
              <label>Instante do degrau t0 (s):<br />
                <input value={t0} onChange={e => setT0(e.target.value)} style={{ width: "100%" }} />
              </label>
            </div>
            <button style={{ marginTop: 16 }} onClick={saveStep}>Salvar</button>
          </>
        ) : bloco.tipo === "constante" ? (
          <>
            <label>Valor constante:<br />
              <input value={valor} onChange={e => setValor(e.target.value)} style={{ width: "100%" }} />
            </label>
            <button style={{ marginTop: 16 }} onClick={saveConst}>Salvar</button>
          </>
        ) : bloco.tipo === "soma" ? (
          <>
            <div>
              <label>Nº de entradas (1 a 3):<br />
                <input
                  type="number"
                  min="1" max="3"
                  value={nEntradas}
                  onChange={e => {
                    const n = Math.min(3, Math.max(1, Number(e.target.value) || 1));
                    setNEntradas(n);
                    setSigns(prev => {
                      const out = (prev || []).slice(0, n);
                      while (out.length < n) out.push(1);
                      return out;
                    });
                  }}
                  style={{ width: "100%" }}
                />
              </label>
            </div>

            {/* Seleção de operação por entrada */}
            <div style={{ marginTop: 12 }}>
              {Array.from({ length: Math.min(3, Math.max(1, nEntradas)) }).map((_, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                  <span>Entrada {i + 1}:</span>
                  <select
                    value={Number(signs[i]) === -1 ? -1 : 1}
                    onChange={e => {
                      const v = Number(e.target.value);
                      setSigns(prev => {
                        const arr = prev.slice();
                        arr[i] = (v === -1 ? -1 : 1);
                        return arr;
                      });
                    }}
                  >
                    <option value={1}>+</option>
                    <option value={-1}>-</option>
                  </select>
                </div>
              ))}
            </div>

            <button style={{ marginTop: 16 }} onClick={saveSum}>Salvar</button>
          </>
        ) : bloco.tipo === "ganho" ? (
          <>
            <label>Ganho k:<br />
              <input value={k} onChange={e => setK(e.target.value)} style={{ width: "100%" }} />
            </label>
            <button style={{ marginTop: 16 }} onClick={saveGain}>Salvar</button>
          </>
        ) : bloco.tipo === "comparador" ? (
          <>
            <label>Ganho k (aplica em fb):<br />
              <input value={k} onChange={e => setK(e.target.value)} style={{ width: "100%" }} />
            </label>
            <div style={{ marginTop: 12 }}>
              <label>G(s) – Numerador (coef. separados por vírgula):<br />
                <input value={num} onChange={e => setNum(e.target.value)} style={{ width: "100%" }} />
              </label>
            </div>
            <div style={{ marginTop: 12 }}>
              <label>G(s) – Denominador (coef. separados por vírgula):<br />
                <input value={den} onChange={e => setDen(e.target.value)} style={{ width: "100%" }} />
              </label>
            </div>
            <button style={{ marginTop: 16 }} onClick={saveComparator}>Salvar</button>
          </>
        ) : (
          <>
            <div>
              <label>Numerador (coef. separados por vírgula):<br />
                <input value={num} onChange={e => setNum(e.target.value)} style={{ width: "100%" }} />
              </label>
            </div>
            <div style={{ marginTop: 12 }}>
              <label>Denominador (coef. separados por vírgula):<br />
                <input value={den} onChange={e => setDen(e.target.value)} style={{ width: "100%" }} />
              </label>
            </div>
            <button style={{ marginTop: 16 }} onClick={saveFT}>Salvar</button>
          </>
        )}
      </div>
    </div>
  );
}

export default function Blocos() {
  const containerWidth = 1400;
  const containerHeight = 800;
  // const blocoWidth = 240;  // substituído por getBlocoDims
  // const blocoHeight = 80;  // substituído por getBlocoDims
  const saidaPos = { x: 1280, y: 350 };

  // Inicia vazio (sem bloco inicial)
  const [blocos, setBlocos] = useState([]);
  const [draggingId, setDraggingId] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [links, setLinks] = useState([]);
  const [linkingFromId, setLinkingFromId] = useState(null);
  const [inspectArc, setInspectArc] = useState(null);
  const [modalBloco, setModalBloco] = useState(null);
  const [saidaModalOpen, setSaidaModalOpen] = useState(false);
  const [deleteMode, setDeleteMode] = useState(false);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [addFilter, setAddFilter] = useState("");

  // Itens do menu (mesmo padrão da página Discreto)
  const menuItems = [
    { label: "Contínuo", href: "/continuo" },
    { label: "Discreto", href: "/discreto" },
    { label: "Alocação de Polos", href: "/alocacao" },
    { label: "Sobre", href: "/sobre" }
  ];

  function deleteBloco(id) {
    setBlocos(b => b.filter(x => x.id !== id));
    setLinks(ls => ls.filter(l => l.from !== id && l.to !== id));
  }
  function deleteLink(idx) {
    setLinks(ls => ls.filter((_, i) => i !== idx));
  }
  function addBloco(tipo = "ft") {
    setBlocos(prev => [
      ...prev,
      tipo === "step"
        ? { id: prev.length ? Math.max(...prev.map(b => b.id)) + 1 : 1, tipo: "step", amp: 1, t0: 0, num: [1], den: [1], x: 100 + 40 * prev.length, y: 100 + 40 * prev.length }
      : tipo === "constante"
        ? { id: prev.length ? Math.max(...prev.map(b => b.id)) + 1 : 1, tipo: "constante", valor: 1, num: [1], den: [1], x: 100 + 40 * prev.length, y: 100 + 40 * prev.length }
      : tipo === "ganho"
        ? { id: prev.length ? Math.max(...prev.map(b => b.id)) + 1 : 1, tipo: "ganho", k: 1, num: [1], den: [1], x: 100 + 40 * prev.length, y: 100 + 40 * prev.length }
      : tipo === "soma"
        ? { id: prev.length ? Math.max(...prev.map(b => b.id)) + 1 : 1, tipo: "soma", nEntradas: 2, signs: [1, 1], num: [1], den: [1], x: 100 + 40 * prev.length, y: 100 + 40 * prev.length }
      : { id: prev.length ? Math.max(...prev.map(b => b.id)) + 1 : 1, tipo: "ft", num: [1], den: [1, 1], x: 100 + 40 * prev.length, y: 100 + 40 * prev.length }
    ]);
    setShowAddMenu(false);
    setAddFilter("");
  }

  function onDragStart(e, id) {
    e.preventDefault();
    const bloco = blocos.find(b => b.id === id);
    if (!bloco) return;
    setDraggingId(id);
    setDragOffset({ x: e.clientX - bloco.x, y: e.clientY - bloco.y });
    document.body.style.userSelect = "none";
  }

  useEffect(() => {
    function onMouseMove(e) {
      if (draggingId !== null) {
        setBlocos(prev =>
          prev.map(b => {
            if (b.id !== draggingId) return b;
            const dims = getBlocoDims(b);
            let newX = e.clientX - dragOffset.x;
            let newY = e.clientY - dragOffset.y;
            newX = Math.max(0, Math.min(containerWidth - dims.width, newX));
            newY = Math.max(0, Math.min(containerHeight - dims.height, newY));
            return { ...b, x: newX, y: newY };
          })
        );
      }
    }
    function onMouseUp() {
      if (draggingId !== null) {
        setDraggingId(null);
        document.body.style.userSelect = "";
      }
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [draggingId, dragOffset]);

  function getDotPos(bloco, type) {
    const { width, height } = getBlocoDims(bloco);
    const x = bloco.x + (type === "input" ? 0 : width);
    const y = bloco.y + height / 2;
    return { x, y };
  }
  function onOutputDotDown(blocoId, e) {
    e.preventDefault(); e.stopPropagation();
    setLinkingFromId(blocoId);
  }
  function onInputDotDown(blocoId, e) {
    e.preventDefault(); e.stopPropagation();
    if (linkingFromId && blocoId !== linkingFromId) {
      setLinks(ls => {
        const exists = ls.some(l => l.from === linkingFromId && l.to === blocoId);
        if (exists || linkingFromId === blocoId) return ls; // evita duplicado/auto-loop
        return [...ls, { from: linkingFromId, to: blocoId }];
      });
    }
    setLinkingFromId(null);
  }

  // Detecta ciclo no grafo (ignora nó "saida")
  const hasCycle = useMemo(() => {
    const adj = new Map();
    blocos.forEach(b => adj.set(b.id, []));
    links.forEach(l => { if (l.to !== "saida" && adj.has(l.from)) adj.get(l.from).push(l.to); });
    const WHITE = 0, GRAY = 1, BLACK = 2;
    const color = new Map(blocos.map(b => [b.id, WHITE]));
    let cycle = false;
    function dfs(v) {
      color.set(v, GRAY);
      for (const w of (adj.get(v) || [])) {
        const c = color.get(w) ?? WHITE;
        if (c === GRAY) { cycle = true; return; }
        if (c === WHITE) { dfs(w); if (cycle) return; }
      }
      color.set(v, BLACK);
    }
    for (const b of blocos) {
      if ((color.get(b.id) ?? WHITE) === WHITE) { dfs(b.id); if (cycle) break; }
    }
    return cycle;
  }, [blocos, links]);

  // Recursão segura (evita loop) — para exibir FT só em grafos acíclicos
  function getAccumulatedTFTo(blocoId, stack = new Set()) {
    if (blocoId === "saida") {
      const entradas = links.filter(l => l.to === "saida").map(l => l.from);
      const entradasTF = entradas.map(id => getAccumulatedTFTo(id, new Set()));
      return sumTFs(entradasTF);
    }
    if (stack.has(blocoId)) return { num: [1], den: [1] }; // corta ciclo
    stack.add(blocoId);

    const entradas = links.filter(l => l.to === blocoId).map(l => l.from);
    if (entradas.length === 0) {
      const bloco = blocos.find(b => b.id === blocoId);
      stack.delete(blocoId);
      return bloco ? { num: bloco.num, den: bloco.den } : { num: [1], den: [1] };
    }
    if (entradas.length === 1) {
      const entradaTF = getAccumulatedTFTo(entradas[0], stack);
      const bloco = blocos.find(b => b.id === blocoId);
      stack.delete(blocoId);
      return bloco ? multiplyTF(entradaTF.num, entradaTF.den, bloco.num, bloco.den) : entradaTF;
    }
    const entradasTF = entradas.map(id => getAccumulatedTFTo(id, stack));
    const soma = sumTFs(entradasTF);
    const bloco = blocos.find(b => b.id === blocoId);
    stack.delete(blocoId);
    return bloco ? multiplyTF(soma.num, soma.den, bloco.num, bloco.den) : soma;
  }

  function getSaidaTF() {
    const saidaLinks = links.filter(l => l.to === "saida");
    if (!saidaLinks.length) return null;
    if (hasCycle) return null; // com feedback, não tenta FT fechada
    return getAccumulatedTFTo("saida", new Set());
  }

  function renderLinks() {
    return (
      <svg className="svg-links" width={containerWidth} height={containerHeight}>
        {links.map((link, i) => {
          const fromBloco = blocos.find(b => b.id === link.from);
          const toBloco = link.to === "saida" ? { x: saidaPos.x, y: saidaPos.y, isSaida: true } : blocos.find(b => b.id === link.to);
          if (!fromBloco || !toBloco) return null;

          const p1 = getDotPos(fromBloco, "output");
          const p2 = link.to === "saida" ? { x: saidaPos.x, y: saidaPos.y + 35 } : getDotPos(toBloco, "input");
          const mx = (p1.x + p2.x) / 2;
          const d = `M${p1.x},${p1.y} C${mx + 60},${p1.y} ${mx - 60},${p2.y} ${p2.x},${p2.y}`;

          const accumulatedTF = getAccumulatedTFTo(link.from);
          let resultTF = accumulatedTF;
          if (toBloco && !toBloco.isSaida) {
            const blocoTo = blocos.find(b => b.id === link.to);
            if (blocoTo) resultTF = multiplyTF(accumulatedTF.num, accumulatedTF.den, blocoTo.num, blocoTo.den);
          }

          const handleArcClick = e => {
            e.stopPropagation();
            if (deleteMode) {
              deleteLink(i);
              setDeleteMode(false);
            } else if (link.to !== "saida") {
              setInspectArc({ from: fromBloco, to: blocos.find(b => b.id === link.to), resultTF, x: mx + 30, y: p1.y - 30, accumulatedTF });
            }
          };

          return (
            <g key={i}>
              <path
                d={d}
                stroke={link.to === "saida" ? "#ff9800" : "#2196f3"}
                strokeWidth="3"
                fill="none"
                markerEnd="url(#arrow)"
                style={link.to !== "saida" ? { cursor: "pointer" } : {}}
                onClick={handleArcClick}
              />
            </g>
          );
        })}
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="5" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L10,5 L0,10" fill="#2196f3" />
          </marker>
        </defs>
      </svg>
    );
  }

  function updateBloco(updated) {
    setBlocos(prev => prev.map(b => b.id === updated.id ? updated : b));
  }

  const saidaTF = getSaidaTF();

  return (
    <div>
      {/* Menu idêntico ao das páginas HTML */}
      <MenuHtmlLike />

      {/* Barra superior apenas com o título (sem o menu antigo) */}
      <div className="top-bar">
        <div className="page-title">Editor de Blocos de Função de Transferência</div>
      </div>

      {/* Faixa de ferramentas */}
      <div className="tools-bar">
        <div className="tools-left">
          <button
            className={"tool-btn add" + (showAddMenu ? " active" : "")}
            title="Adicionar bloco"
            onClick={() => setShowAddMenu(s => !s)}
            aria-label="Adicionar bloco"
          >
            {/* ícone + */}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="11" stroke="currentColor" opacity="0.2"/>
              <rect x="11" y="5" width="2" height="14" rx="1" fill="currentColor"/>
              <rect x="5" y="11" width="14" height="2" rx="1" fill="currentColor"/>
            </svg>
          </button>

          {showAddMenu &&
            <div className="add-menu">
              <input
                className="add-search"
                placeholder="Buscar blocos..."
                value={addFilter}
                onChange={e => setAddFilter(e.target.value)}
              />
              <div className="add-grid">
                {[
                  { key: "ft", label: "Função de Transferência", color: "#1976d2" },
                  { key: "step", label: "Entrada Degrau (Step)", color: "#388e3c" },
                  { key: "soma", label: "Somador", color: "#7b1fa2" },
                  { key: "ganho", label: "Ganho (K)", color: "#e65100" },
                  { key: "constante", label: "Constante", color: "#455a64" },
                ]
                  .filter(it => it.label.toLowerCase().includes(addFilter.toLowerCase()))
                  .map(it => (
                    <button
                      key={it.key}
                      className="add-item"
                      style={{ borderColor: it.color }}
                      onClick={() => addBloco(it.key)}
                    >
                      {it.label}
                    </button>
                  ))
                }
              </div>
            </div>
          }
        </div>

        <div className="tools-right">
          <button
            className={"tool-btn danger" + (deleteMode ? " active" : "")}
            title={deleteMode ? "Sair do modo deletar" : "Modo deletar: clique para ativar"}
            onClick={() => setDeleteMode(m => !m)}
            aria-label="Modo deletar"
          >
            {/* ícone – */}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="11" stroke="currentColor" opacity="0.2"/>
              <rect x="5" y="11" width="14" height="2" rx="1" fill="currentColor"/>
            </svg>
          </button>
        </div>
      </div>

      {hasCycle && (
        <div style={{ position: "fixed", left: 24, top: 24, zIndex: 200, background: "#fff3cd", border: "1px solid #ffecb5", color: "#856404", padding: "8px 12px", borderRadius: 6, boxShadow: "0 2px 8px #0001" }}>
          Feedback detectado. A FT total não é exibida. Clique na “Saída” para simular.
        </div>
      )}
      <div className="blocos-container" style={{ width: containerWidth, height: containerHeight }}>
        {renderLinks()}

        {blocos.map(bloco =>
          <Bloco
            key={bloco.id}
            bloco={bloco}
            onClick={() => {
              if (deleteMode) { deleteBloco(bloco.id); setDeleteMode(false); }
              else { setModalBloco(bloco); }
            }}
            onDragStart={onDragStart}
            onInputDotDown={onInputDotDown}
            onOutputDotDown={onOutputDotDown}
            isInputActive={!!linkingFromId}
            isOutputActive={linkingFromId === bloco.id}
            dragging={draggingId === bloco.id}
            deleteMode={deleteMode}
            onDelete={(id) => { deleteBloco(id); setDeleteMode(false); }}
          />
        )}

        {/* FT total apenas se não houver ciclo */}
        {!hasCycle && saidaTF &&
          <div style={{
            position: "absolute", left: saidaPos.x + 35 - 130, top: saidaPos.y - 60, width: 260,
            color: "#ff9800", fontSize: "1.1em", fontFamily: "serif", background: "#fffbe6", borderRadius: 8,
            padding: "8px 12px", boxShadow: "0 2px 8px #0001", zIndex: 6, wordBreak: "break-word", textAlign: "center"
          }}>
            <b>Resultado em série:</b><br />
            <span>G<sub>total</sub>(s) = (<span>{latexPoly(saidaTF.num)}</span>) / (<span>{latexPoly(saidaTF.den)}</span>)</span>
          </div>
        }

        <SaidaBloco
          pos={saidaPos}
          onInputDotDown={onInputDotDown}
          isInputActive={!!linkingFromId}
          onSaidaClick={() => setSaidaModalOpen(true)}
        />
      </div>

      {inspectArc &&
        <ArcInspectModal
          left={inspectArc.x}
          top={inspectArc.y}
          fromBloco={inspectArc.from}
          toBloco={inspectArc.to}
          resultTF={inspectArc.resultTF}
          onClose={() => setInspectArc(null)}
          accumulatedTF={inspectArc.accumulatedTF}
        />
      }

      {modalBloco &&
        <ConfigModal
          bloco={modalBloco}
          onClose={() => setModalBloco(null)}
          onSave={updateBloco}
        />
      }

      <SaidaGraphModal
        open={saidaModalOpen}
        onClose={() => setSaidaModalOpen(false)}
        graph={{ blocos, links }}
      />
    </div>
  );
}