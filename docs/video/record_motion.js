// Enregistre les séquences animées de motion.html : node docs/video/record_motion.js <dossier de sortie>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const out = process.argv[2];
const DUREES = { intro: 30, trace: 22, resultats: 34, fin: 8 };
(async () => {
  const b = await chromium.launch();
  for (const [scene, d] of Object.entries(DUREES)) {
    const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
    const p = await ctx.newPage();
    await p.goto('file://' + path.resolve(__dirname, 'motion.html') + '?scene=' + scene);
    await p.waitForTimeout(d * 1000 + 400);
    const v = p.video(); await ctx.close();
    fs.renameSync(await v.path(), `${out}/${scene}.webm`);
    console.log(scene, d);
  }
  await b.close();
})().catch((e) => { console.error('ECHEC', e.message); process.exit(1); });
