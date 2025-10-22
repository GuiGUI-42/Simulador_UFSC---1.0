// Cria uma instância do Fastify com logs habilitados
const fastify = require('fastify')({ logger: true });
const cors = require('@fastify/cors');

// Registra CORS (aceita qualquer origem)
fastify.register(cors, {
  origin: '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type']
});
// Habilita parse de application/x-www-form-urlencoded (se necessário)
fastify.register(require('@fastify/formbody'));

/**
 * Rota principal: POST /atualizar_discreto
 * - Entrada (JSON): { Ts, polos, zeros }
 *   Ts: período de amostragem (s)
 *   polos: polos do contínuo (reais)
 *   zeros: zeros do contínuo (reais)
 * - Saída: objetos para LaTeX e dados de gráfico (contínuo e amostrado)
 */
fastify.post('/atualizar_discreto', async (request, reply) => {
  const { Ts = 0.1, polos = [], zeros = [] } = request.body || {};

  // Normaliza/filtra entradas
  const poles = Array.isArray(polos) ? polos.map(Number).filter(Number.isFinite) : [];
  const zerosC = Array.isArray(zeros) ? zeros.map(Number).filter(Number.isFinite) : [];

  // Garante Ts > 0 para não dividir por zero
  const TsNum = Number(Ts);
  const TsSafe = Number.isFinite(TsNum) && TsNum > 0 ? TsNum : 1e-3;

  // Helpers ---------------------------------------------------

  // Formata número com d casas decimais (para exibir em LaTeX)
  const fmt = (n, d = 2) => Number(n).toFixed(d);

  /**
   * Constrói polinômio a partir das raízes (em potências decrescentes).
   * Ex.: roots=[r1, r2] -> (s - r1)(s - r2) = s^2 - (r1+r2)s + r1*r2
   * Retorna array de coeficientes [1, a1, a2, ...].
   */
  const polyFromRoots = (roots) => {
    // Começa com o polinômio constante 1
    let c = [1];
    for (const r of roots) {
      // Convolução com (s - r)
      const next = new Array(c.length + 1).fill(0);
      for (let i = 0; i < c.length; i++) {
        next[i] += c[i];          // termo multiplicado por s
        next[i + 1] += -r * c[i]; // termo constante (-r)
      }
      c = next;
    }
    return c.map(Number);
  };

  /**
   * Gera as strings em LaTeX para G(s) e G(z) (forma fatorada):
   * - G(s) = produto dos fatores (s - z_i) / produto (s - p_i)
   * - G(z) (método ilustrativo): mapeia polos/zeros por z = e^{p Ts}
   *   e escreve como produto (1 - alpha z^{-1}) no discreto.
   * Observação: é apenas para exibição; não calcula ganho de pré‑warp etc.
   */
  const buildLatex = () => {
    const fmt = (n, d = 2) => Number(n).toFixed(d);
    const factorS = (v) => `(s${v >= 0 ? '-' : '+'}${fmt(Math.abs(v))})`;
    const factorZinv = (alpha) => `(1 - ${fmt(alpha)}\\,z^{-1})`;

    const num_s = zerosC.length ? zerosC.map(factorS).join('\\,\\cdot\\,') : '1';
    const den_s = poles.length ? poles.map(factorS).join('\\,\\cdot\\,') : '1';

    const zPoles = poles.map(p => Math.exp(p * TsSafe));
    const zZeros = zerosC.map(z => Math.exp(z * TsSafe));

    const num_z = zZeros.length ? zZeros.map(factorZinv).join('\\,\\cdot\\,') : '1';
    const den_z = zPoles.length ? zPoles.map(factorZinv).join('\\,\\cdot\\,') : '1';

    return {
      latex_Gs: `G(s) = \\dfrac{${zerosC.length ? num_s : '1'}}{${poles.length ? den_s : '1'}}`,
      latex_Gz: `G(z) = \\dfrac{${zZeros.length ? num_z : '1'}}{${zPoles.length ? den_z : '1'}}`,
    };
  };

  const { latex_Gs, latex_Gz } = buildLatex();

  // Validação: FT imprópria (mais zeros que polos) -> retorna warning e não sobrescreve gráficos do frontend
  if (zerosC.length > poles.length) {
    return reply.send({
      latex_Gs,
      latex_Gz,
      warning: 'A FT é imprópria (mais zeros do que polos). Remova zeros ou adicione polos.',
    });
  }

  // Definição do horizonte de simulação contínua --------------------------
  // Se houver polos estáveis reais (p<0), usa a constante de tempo dominante.
  // Caso não haja polos, usa aDom=1 para ter um horizonte finito padrão.
  const realPartsNeg = poles.map(p => -Number(p)).filter(v => v > 0);
  const aDom = realPartsNeg.length ? Math.min(...realPartsNeg) : 1; // constante de tempo ~ 1/aDom
  const Tend = Math.max(5 / aDom, 5); // simula ~5 constantes de tempo (mínimo 5s)
  const dt = Tend / 800; // passo do integrador de Euler (resolução do contínuo)

  // Polinômios num/den (potências decrescentes) ----------------------------
  const den = polyFromRoots(poles); // ex.: [1, a1, ..., an]
  const n = Math.max(1, den.length - 1); // ordem do sistema (>=1)
  let num = polyFromRoots(zerosC);       // pode ter ordem menor
  // Faz padding do numerador para ter tamanho n+1 (alinha com o denominador)
  if (num.length < n + 1) num = new Array(n + 1 - num.length).fill(0).concat(num);

  // Realização em forma canônica controlável -------------------------------
  // den = 1 + a1 s^{-1} + ... + an s^{-n} (em potências decrescentes de s)
  const aCoe = den.slice(1); // [a1..an]
  // Matriz A com 1 na superdiagonal e última linha = -[an ... a1]
  const A = Array.from({ length: n }, () => Array(n).fill(0));
  for (let i = 0; i < n - 1; i++) A[i][i + 1] = 1;
  A[n - 1] = aCoe.slice().reverse().map(v => -v);

  // Vetor B (apenas último elemento = 1)
  const B = Array.from({ length: n }, (_, i) => (i === n - 1 ? 1 : 0));
  // Ganho direto D (coeficiente constante do numerador)
  const D = num[num.length - 1];
  // Vetor C conforme relação entre coeficientes (mantendo den monico)
  // C = [b0 - a1*D, b1 - a2*D, ..., b_{n-1} - an*D]
  const C = aCoe.map((ai, i) => (num[i] - ai * D));

  // Simulação contínua (resposta ao degrau unitário) -----------------------
  // Integração simples por Euler explícito: x_{k+1} = x_k + dt(Ax_k + Bu)
  const xCont = []; // instantes de tempo do contínuo
  const yCont = []; // saída contínua
  for (let t = 0; t <= Tend + 1e-12; t += dt) {
    xCont.push(Number(t.toFixed(4)));
  }

  // Estado inicial zero
  let x = Array(n).fill(0);
  for (let i = 0; i < xCont.length; i++) {
    // Saída y = Cx + Du, com u=1 (degrau)
    const y = C.reduce((acc, c, j) => acc + c * x[j], 0) + D * 1;
    yCont.push(Number(y.toFixed(6)));

    // Evolução do estado com u=1
    const Ax = Array(n).fill(0);
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) Ax[r] += A[r][c] * x[c];
    }
    for (let r = 0; r < n; r++) Ax[r] += B[r] * 1; // adiciona Bu
    for (let r = 0; r < n; r++) x[r] = x[r] + dt * Ax[r];
  }

  // Amostragem discreta (usa TsSafe)
  const N = Math.max(1, Math.floor(Tend / TsSafe));
  const xDisc = [];
  const yDisc = [];
  for (let k = 0; k <= N; k++) {
    const tk = k * TsSafe;
    const idx = Math.min(Math.round(tk / dt), yCont.length - 1);
    xDisc.push(Number(tk.toFixed(4)));
    yDisc.push(Number(yCont[idx].toFixed(6)));
  }

  reply.send({
    latex_Gs,
    latex_Gz,
    plot_continuo: { x: xCont, y: yCont },
    plot_discreto: { x: xDisc, y: yDisc },
    horizonte: Tend
  });
});

/**
 * Nova rota: POST /simular_blocos
 * body: { num: number[], den: number[], t_final?: number, n_points?: number }
 * Retorna resposta ao degrau contínua: { t: number[], y: number[] }
 */
fastify.post('/simular_blocos', async (request, reply) => {
  try {
    const body = request.body || {};
    if (Array.isArray(body.blocks) && Array.isArray(body.links)) {
      const blocks = body.blocks;
      const links = body.links;
      const T = Math.max(1e-6, Number(body.t_final) || 10);
      const h = Math.max(1e-6, Number(body.dt) || 0.01);
      const steps = Math.max(2, Math.floor(T / h));

      function realizeTF(num = [1], den = [1, 1]) {
        const denArr = (den || [1, 1]).map(Number);
        const numArr = (num || [1]).map(Number);
        if (!denArr.length || denArr.every(v => Math.abs(v) < 1e-12)) {
          return { A: [[0]], B: [0], C: [0], D: 0, n: 1, x: [0] };
        }
        const k = denArr[0];
        const denM = denArr.map(v => v / k);
        let numM = numArr.map(v => v / k);
        const n = Math.max(1, denM.length - 1);
        if (numM.length < n + 1) numM = new Array(n + 1 - numM.length).fill(0).concat(numM);
        const a = denM.slice(1).slice().reverse();
        const D = numM[0];
        const b = numM.slice(1).slice().reverse();
        const A = Array.from({ length: n }, () => Array(n).fill(0));
        for (let i = 0; i < n - 1; i++) A[i][i + 1] = 1;
        A[n - 1] = a.map(v => -v);
        const B = Array.from({ length: n }, (_, i) => (i === n - 1 ? 1 : 0));
        const C = b.map((bi, i) => bi - D * a[i]);
        return { A, B, C, D, n, x: Array(n).fill(0) };
      }

      // Instâncias runtime
      const runtime = new Map();
      for (const b of blocks) {
        if (b.tipo === 'ft') {
          const sys = realizeTF(b.num || [1], b.den || [1, 1]);
          runtime.set(b.id, { kind: 'ft', sys });
        } else if (b.tipo === 'integrador') runtime.set(b.id, { kind: 'integrador', x: 0 });
        else if (b.tipo === 'atraso') runtime.set(b.id, { kind: 'atraso', z: 0 });
        else if (b.tipo === 'ganho') runtime.set(b.id, { kind: 'ganho', k: Number(b.k ?? 1) });
        else if (b.tipo === 'soma') runtime.set(b.id, { kind: 'soma', k: Number(b.k ?? -1) });
        else if (b.tipo === 'comparador') { // compatível com diagramas antigos
          const num = Array.isArray(b.num) ? b.num.map(Number) : [1];
          const den = Array.isArray(b.den) ? b.den.map(Number) : [1];
          const hasDyn = (den?.length || 0) > 1;
          const sys = hasDyn ? realizeTF(num, den) : null;
          runtime.set(b.id, { kind: 'comparador', k: Number(b.k ?? -1), sys });
        }
        else if (b.tipo === 'step' || b.tipo === 'degrau') runtime.set(b.id, { kind: 'step', amp: Number(b.amp ?? 1), t0: Number(b.t0 ?? 0) });
        else if (b.tipo === 'constante') runtime.set(b.id, { kind: 'constante', c: Number(b.valor ?? 0) });
        else runtime.set(b.id, { kind: 'ganho', k: 1 });
      }

      // Entradas por nó
      const incoming = new Map();
      for (const b of blocks) incoming.set(b.id, []);
      for (const l of links) {
        if (l.to === 'saida') continue;
        if (!incoming.has(l.to)) incoming.set(l.to, []);
        incoming.get(l.to).push(l.from);
      }
      const toSaida = links.filter(l => l.to === 'saida').map(l => l.from);

      // u do somador (2ª entrada ponderada por k)
      function sumInput(id, outputs) {
        const preds = incoming.get(id) || [];
        const r = runtime.get(id);
        let u = 0;
        for (let i = 0; i < preds.length; i++) {
          const w = (i === 1) ? (r?.k ?? -1) : 1;
          u += w * (outputs.get(preds[i]) ?? 0);
        }
        return u;
      }
      // u do comparador antigo (ref + k·fb + resto)
      function comparatorInput(id, outputs) {
        const preds = incoming.get(id) || [];
        const r = runtime.get(id);
        const ref = preds[0] != null ? (outputs.get(preds[0]) ?? 0) : 0;
        const fb  = preds[1] != null ? (outputs.get(preds[1]) ?? 0) : 0;
        let rest = 0; for (let i = 2; i < preds.length; i++) rest += (outputs.get(preds[i]) ?? 0);
        return ref + (r?.k ?? -1) * fb + rest;
      }

      // Avaliação (sem atualizar estado)
      function evalBlockOutput(id, u, time) {
        const r = runtime.get(id);
        if (!r) return 0;
        switch (r.kind) {
          case 'ganho': return r.k * u;
          case 'constante': return r.c;
          case 'step': return (time >= r.t0) ? r.amp : 0;
          case 'soma': return u;
          case 'comparador':
            if (r.sys) {
              const { C, D, x } = r.sys;
              let y = D * u; for (let i = 0; i < C.length; i++) y += C[i] * x[i];
              return y;
            }
            return u;
          case 'atraso': return r.z;
          case 'integrador': return r.x;
          case 'ft': {
            const { C, D, x } = r.sys;
            let y = D * u; for (let i = 0; i < C.length; i++) y += C[i] * x[i];
            return y;
          }
          default: return u;
        }
      }

      // Atualização de estado
      function updateState(id, u) {
        const r = runtime.get(id);
        if (!r) return;
        switch (r.kind) {
          case 'integrador': r.x = r.x + h * u; break;
          case 'atraso': r.z = u; break;
          case 'comparador':
          case 'ft': {
            if (!r.sys) break;
            const { A, B, x } = r.sys;
            const Ax = Array(x.length).fill(0);
            for (let i = 0; i < A.length; i++) {
              for (let j = 0; j < A[0].length; j++) Ax[i] += A[i][j] * x[j];
              Ax[i] += B[i] * u;
            }
            for (let i = 0; i < x.length; i++) r.sys.x[i] = x[i] + h * Ax[i];
            break;
          }
        }
      }

      // SCCs algébricos (somente nós estáticos)
      const adj = new Map();
      for (const b of blocks) adj.set(b.id, []);
      for (const l of links) if (l.to !== 'saida') (adj.get(l.from) || []).push(l.to);

      const isStatic = (v) => {
        const r = runtime.get(v);
        if (!r) return true;
        if (r.kind === 'comparador') return !r.sys;
        return r.kind === 'ganho' || r.kind === 'soma' || r.kind === 'constante' || r.kind === 'step';
      };

      // Constrói grafo apenas com nós estáticos (ignora 'saida')
      const staticNodes = blocks.map(b => b.id).filter(id => isStatic(id));
      const sAdj = new Map(staticNodes.map(id => [id, []]));
      for (const l of links) {
        if (l.to === 'saida') continue;
        if (sAdj.has(l.from) && sAdj.has(l.to)) sAdj.get(l.from).push(l.to);
      }

      // Tarjan para SCCs
      let index = 0;
      const indices = new Map();
      const lowlink = new Map();
      const onStack = new Map();
      const S = [];
      const sccs = [];

      function strongconnect(v) {
        indices.set(v, index);
        lowlink.set(v, index);
        index++;
        S.push(v);
        onStack.set(v, true);

        for (const w of (sAdj.get(v) || [])) {
          if (!indices.has(w)) {
            strongconnect(w);
            lowlink.set(v, Math.min(lowlink.get(v), lowlink.get(w)));
          } else if (onStack.get(w)) {
            lowlink.set(v, Math.min(lowlink.get(v), indices.get(w)));
          }
        }

        if (lowlink.get(v) === indices.get(v)) {
          const comp = [];
          let w;
          do {
            w = S.pop();
            onStack.set(w, false);
            comp.push(w);
          } while (w !== v);
          sccs.push(comp);
        }
      }

      for (const v of staticNodes) if (!indices.has(v)) strongconnect(v);

      // Componentes algébricos: SCCs com mais de 1 nó ou auto-loop
      const algebraicSCCs = sccs.filter(comp => {
        if (comp.length > 1) return true;
        const v = comp[0];
        return (sAdj.get(v) || []).includes(v);
      });

      function solveAlgebraic(outputs, time, maxIter = 60, tol = 1e-6, relax = 0.5) {
        for (const comp of algebraicSCCs) {
          for (let it = 0; it < maxIter; it++) {
            let maxDelta = 0;
            for (const id of comp) {
              const r = runtime.get(id);
              let u = 0;
              if (r?.kind === 'soma') u = sumInput(id, outputs);
              else if (r?.kind === 'comparador') u = comparatorInput(id, outputs);
              else {
                const preds = incoming.get(id) || [];
                for (const p of preds) u += (outputs.get(p) ?? 0);
              }
              const yOld = outputs.get(id) ?? 0;
              const yNew = evalBlockOutput(id, u, time);
              const y = yOld + relax * (yNew - yOld);
              outputs.set(id, y);
              maxDelta = Math.max(maxDelta, Math.abs(y - yOld));
            }
            if (maxDelta < tol) break;
          }
        }
      }

      // Simulação
      const t = [];
      const y = [];
      let outputs = new Map(blocks.map(b => [b.id, 0]));

      for (let kstep = 0; kstep <= steps; kstep++) {
        const tk = Number((kstep * h).toFixed(6));
        t.push(tk);

        solveAlgebraic(outputs, tk);

        // Avalia blocos
        for (const b of blocks) {
          const r = runtime.get(b.id);
          let u = 0;
          if (r?.kind === 'soma') u = sumInput(b.id, outputs);
          else if (r?.kind === 'comparador') u = comparatorInput(b.id, outputs);
          else {
            const preds = incoming.get(b.id) || [];
            for (const p of preds) u += (outputs.get(p) ?? 0);
          }
          outputs.set(b.id, evalBlockOutput(b.id, u, tk));
        }

        // Atualiza estados
        for (const b of blocks) {
          const r = runtime.get(b.id);
          let u = 0;
          if (r?.kind === 'soma') u = sumInput(b.id, outputs);
          else if (r?.kind === 'comparador') u = comparatorInput(b.id, outputs);
          else {
            const preds = incoming.get(b.id) || [];
            for (const p of preds) u += (outputs.get(p) ?? 0);
          }
          updateState(b.id, u);
        }

        // Saída
        let yk = 0; for (const from of toSaida) yk += (outputs.get(from) ?? 0);
        y.push(Number(yk.toFixed(6)));
      }

      return reply.send({ t, y });
    }

    // FT simples (usa a mesma realização)
    const { num = [1], den = [1, 1], t_final = 40, n_points = 200 } = body;
    const numArr = Array.isArray(num) ? num.map(Number).filter(Number.isFinite) : [1];
    const denArr = Array.isArray(den) ? den.map(Number).filter(Number.isFinite) : [1, 1];
    if (!denArr.length || denArr.every(v => Math.abs(v) < 1e-12)) {
      return reply.status(400).send({ message: "Denominador inválido." });
    }

    const sys = realizeTF(numArr, denArr);
    const { A, B, C, D, n } = sys;

    const Tfinal = Math.max(0.001, Number(t_final) || 40);
    const Np = Math.max(2, Math.floor(Number(n_points) || 200));
    const dt = Tfinal / (Np - 1);

    const t = [];
    const y = [];
    let x = Array(n).fill(0);

    for (let i = 0; i < Np; i++) {
      const ti = i * dt;
      t.push(Number(ti.toFixed(6)));
      const yk = C.reduce((acc, c, j) => acc + c * x[j], 0) + D * 1;
      y.push(Number(yk.toFixed(6)));

      const Ax = Array(n).fill(0);
      for (let r = 0; r < n; r++) {
        for (let c = 0; c < n; c++) Ax[r] += A[r][c] * x[c];
        Ax[r] += B[r] * 1;
      }
      for (let r = 0; r < n; r++) x[r] = x[r] + dt * Ax[r];
    }

    reply.send({ t, y });
  } catch (e) {
    request.log.error(e);
    reply.status(500).send({ message: "Falha ao simular." });
  }
});

// Rota de saúde para teste rápido
fastify.get('/health', async (request, reply) => reply.send({ ok: true }));

// Inicializa o servidor -----------------------------------------------------
const PORT = process.env.PORT || 5000;
fastify.listen({ port: PORT, host: '0.0.0.0' }, (err) => {
  if (err) {
    fastify.log.error(err);
    process.exit(1);
  }
  console.log(`Servidor Fastify rodando em http://localhost:${PORT}`);
});
