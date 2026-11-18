// Enregistre l'interface réelle scène par scène (Playwright), avec un bandeau de texte en bas.
// node docs/video/record_ui.js <dossier de sortie>   (interface lancée sur le port 8765, STATE_DIR vide)
const { chromium } = require('playwright');
const fs = require('fs');
const out = process.argv[2];
const W = 1920, H = 1080, BAR = 150;

const OVERLAY = `
  const z = document.querySelector('[data-testid="stApp"]');
  z.style.zoom = '1.5';
  const st = document.createElement('style');
  st.textContent = '[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stStatusWidget"]{visibility:hidden}'
    + '[data-testid="stMainBlockContainer"]{padding-bottom:${BAR + 40}px !important;padding-top:28px !important}'
    + '#cap{position:fixed;left:0;right:0;bottom:0;height:${BAR}px;background:#12372a;color:#fff;display:flex;align-items:center;'
    + 'justify-content:center;font:700 44px Carlito,Arial,sans-serif;z-index:2147483000;text-align:center;padding:0 60px}'
    + '#cur{position:fixed;width:26px;height:26px;border-radius:50%;background:rgba(232,137,43,.85);border:3px solid #fff;'
    + 'z-index:2147483600;pointer-events:none;transform:translate(-50%,-50%);transition:left .35s ease,top .35s ease;left:960px;top:500px}';
  document.head.appendChild(st);
  const c = document.createElement('div'); c.id = 'cap'; document.body.appendChild(c);
  const m = document.createElement('div'); m.id = 'cur'; document.body.appendChild(m);
`;

(async () => {
  const b = await chromium.launch();
  const marks = {};
  async function scene(name, fn) {
    const ctx = await b.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: out, size: { width: W, height: H } } });
    const p = await ctx.newPage();
    const t0 = Date.now();
    await p.goto('http://localhost:8765'); await p.waitForSelector('textarea');
    await p.evaluate(OVERLAY); await p.waitForTimeout(600);
    const h = {
      p,
      cap: (t) => p.evaluate((t) => { document.getElementById('cap').textContent = t; }, t),
      wait: (ms) => p.waitForTimeout(ms),
      async settle() {
        await p.waitForTimeout(700);
        for (let i = 0; i < 300; i++) { if (!(await p.locator('[data-testid="stSpinner"]').count())) break; await p.waitForTimeout(300); }
        await p.waitForTimeout(900);
      },
      async point(loc) {
        loc = loc.first();
        for (let i = 0; i < 6; i++) {  // Streamlit redessine la page : on réessaie si l'élément a été remplacé
          try { await loc.waitFor({ state: 'visible', timeout: 15000 }); await loc.evaluate((el) => el.scrollIntoView({ block: 'center', behavior: 'smooth' })); break; }
          catch (e) { await p.waitForTimeout(500); }
        }
        await p.waitForTimeout(700);
        const bx = await loc.boundingBox();
        const x = bx.x + Math.min(bx.width / 2, 160), y = bx.y + bx.height / 2;
        await p.evaluate(([x, y]) => { const m = document.getElementById('cur'); m.style.left = x + 'px'; m.style.top = y + 'px'; }, [x, y]);
        await p.waitForTimeout(550);
      },
      async click(loc) { await h.point(loc); await loc.first().click(); },
      async level(label) { await h.click(p.locator('[data-testid="stSidebar"] label').filter({ hasText: label }).first()); await h.settle(); },
      async ask(q) {
        const ta = p.locator('textarea[aria-label="Question"]').first();
        await h.click(ta); await ta.fill(''); await ta.pressSequentially(q, { delay: 22 }); await ta.press('Control+Enter'); await p.waitForTimeout(500);
        await h.click(p.getByRole('button', { name: 'Envoyer' })); await h.settle(); await h.answer();
      },
      // question choisie parmi les suggestions de l'interface (thème, puis puce), puis envoyée
      async suggest(theme, text) {
        await h.click(p.locator('.st-key-sugg [data-testid="stButtonGroup"]').first().getByText(theme, { exact: true }));
        await h.settle();
        await h.click(p.locator('.st-key-sugg').getByText(text).first()); await h.settle(); await p.waitForTimeout(600);
        await h.click(p.getByRole('button', { name: 'Envoyer' })); await h.settle(); await h.answer();
      },
      // amène la réponse au centre de l'écran
      async answer() {
        const a = p.locator('[class*="st-key-answer_"]').first();
        if (await a.count()) { await a.evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'smooth' })); await p.waitForTimeout(900); }
      },
      text: () => p.locator('[data-testid="stMain"]').innerText(),
      mark: () => (Date.now() - t0) / 1000,
    };
    marks[name] = { start: h.mark() };
    const res = await fn(h);
    marks[name].end = h.mark(); marks[name].info = res || null;
    const v = p.video(); await ctx.close();
    fs.renameSync(await v.path(), `${out}/${name}.webm`);
    console.log(name, JSON.stringify(marks[name]));
  }

  // échauffement hors enregistrement : le premier appel charge le modèle d'embeddings
  { const ctx = await b.newContext(); const p = await ctx.newPage(); await p.goto('http://localhost:8765'); await p.waitForSelector('textarea');
    await p.locator('[data-testid="stSidebar"] label').filter({ hasText: '1 · RAG' }).first().click(); await p.waitForTimeout(1500);
    const ta = p.locator('textarea[aria-label="Question"]').first(); await ta.fill('Combien de joueurs par équipe ?'); await ta.press('Control+Enter');
    await p.getByRole('button', { name: 'Envoyer' }).click(); await p.waitForTimeout(1500);
    for (let i = 0; i < 400; i++) { if (!(await p.locator('[data-testid="stSpinner"]').count())) break; await p.waitForTimeout(500); }
    await ctx.close(); }

  const only = process.argv[3] ? process.argv[3].split(',') : null;
  const run = async (name, fn) => { if (!only || only.includes(name)) await scene(name, fn); };

  await run('s0', async (h) => {
    await h.cap('Des questions proposées par thème : un clic choisit aussi le bon niveau'); await h.wait(1200);
    await h.point(h.p.locator('.st-key-sugg [data-testid="stButtonGroup"]').first()); await h.wait(1500);
    await h.click(h.p.locator('.st-key-sugg').getByText('Données de match', { exact: true })); await h.settle(); await h.wait(1600);
    await h.cap('Et les 262 matchs des données StatsBomb, à analyser en un clic'); 
    await h.point(h.p.getByText('Matchs à analyser')); await h.wait(1200);
    await h.point(h.p.locator('.st-key-sugg').getByText('Carte des tirs', { exact: true })); await h.wait(2600);
    await h.click(h.p.locator('.st-key-sugg').getByText('Lois du jeu', { exact: true })); await h.settle(); await h.wait(800);
  });
  await run('s1', async (h) => {
    await h.cap('Niveau 1 · RAG : la réponse cite sa source');
    await h.suggest('Lois du jeu', 'À quelle distance du ballon doivent se placer');
    await h.wait(1800);
    await h.click(h.p.locator('[data-testid="stExpander"] summary').first()); await h.wait(600);
    await h.cap("L'extrait cité vient des lois du jeu : la réponse est vérifiable"); await h.wait(3800);
    await h.point(h.p.getByText('Coût équivalent').first()); await h.cap('Tokens, coût et latence sont affichés à chaque requête'); await h.wait(3000);
  });
  await run('s2', async (h) => {
    await h.cap('Une question dont la réponse est absente des documents');
    await h.suggest('Cas limites', 'Quelle est la durée maximale');
    await h.cap("Abstention : le système dit qu'il ne sait pas, sans inventer"); await h.wait(4500);
  });
  await run('s3', async (h) => {
    await h.cap('Une tâche en plusieurs étapes : préparer et publier un rapport'); await h.level('2 · Agent');
    await h.ask("Prépare et publie le rapport d'avant-match Angleterre - Espagne avec le nombre de tirs cadrés de l'Espagne lors de la finale de l'Euro 2024.");
    await h.cap("L'agent a enchaîné ses outils sur les données StatsBomb"); await h.wait(1200);
    await h.click(h.p.getByText(/Appels d'outils \(\d+\)/)); await h.wait(4200);
    await h.click(h.p.getByText(/Appels d'outils \(\d+\)/)); await h.wait(500);
    await h.point(h.p.getByText('Action irréversible demandée')); await h.cap("Publier est irréversible : rien n'est fait sans validation"); await h.wait(4200);
    await h.point(h.p.getByRole('button', { name: 'Valider' })); await h.cap("Le rapport proposé est relu, puis validé par l'utilisateur"); await h.wait(2600);
    await h.p.getByRole('button', { name: 'Valider' }).click(); await h.settle();
    await h.point(h.p.getByText('Rapport publié')); await h.cap('Action validée : le rapport est publié, la validation est tracée'); await h.wait(3800);
    const m = (await h.text()).match(/traces\/(\S+\.jsonl)/);
    return m ? m[1] : null;
  });
  await run('s4', async (h) => {
    await h.cap('Les chiffres du rapport sont calculés par le code, pas par le modèle');
    await h.click(h.p.getByRole('tab', { name: 'Rapports publiés' })); await h.settle();
    await h.click(h.p.locator('[data-testid="stExpander"] summary').last()); await h.settle(); await h.wait(2200);
    await h.p.mouse.move(1100, 500);
    for (let i = 0; i < 5; i++) { await h.p.mouse.wheel(0, 420); await h.wait(1100); }
    await h.cap('Forme, confrontations, cartes des tirs, pronostic, puis export PDF'); await h.wait(1200);
    for (let i = 0; i < 6; i++) { await h.p.mouse.wheel(0, 420); await h.wait(1000); }
    await h.wait(1500);
  });
  await run('s5', async (h) => {
    await h.cap('Une demande ambiguë : aucune affiche n\'est donnée'); await h.level('2 · Agent');
    let invented = false, last = 0;  // le niveau 2 varie d'un essai à l'autre : on garde le dernier essai au montage
    for (let k = 0; k < 9 && !invented; k++) {
      last = h.mark();
      await h.ask("Publie le rapport d'avant-match de la Coupe du monde 2026.");
      invented = (await h.p.getByRole('button', { name: 'Refuser' }).count()) > 0;
    }
    if (invented) {
      await h.point(h.p.getByText('Action irréversible demandée')); await h.cap("Niveau 2 : l'agent choisit lui-même une affiche et veut la publier"); await h.wait(4500);
      await h.click(h.p.getByRole('button', { name: 'Refuser' })); await h.settle(); await h.wait(1200);
    }
    await h.cap('Niveau 3 · Agent avec plan : décider avant d\'agir'); await h.level('3 · Agent avec plan');
    await h.ask("Publie le rapport d'avant-match de la Coupe du monde 2026.");
    await h.cap('Une seule étape, aucun outil : il demande quelle affiche'); await h.wait(5000);
    return { invented, last };
  });
  const old = fs.existsSync(`${out}/marks.json`) ? JSON.parse(fs.readFileSync(`${out}/marks.json`)) : {};
  fs.writeFileSync(`${out}/marks.json`, JSON.stringify({ ...old, ...marks }, null, 1));
  await b.close();
})().catch((e) => { console.error('ECHEC', e.message); process.exit(1); });
