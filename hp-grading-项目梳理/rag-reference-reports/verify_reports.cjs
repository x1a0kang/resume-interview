const {chromium} = require('C:/Users/juruikang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const dir=__dirname;
(async()=>{
 const browser=await chromium.launch({headless:true});
 const results=[];
 for(const file of ['index.html','modular-rag.html','paismart.html','hp-optimization.html']){
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:1000},colorScheme:'light',reducedMotion:'reduce'});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(pathToFileURL(path.join(dir,file)).href);
   const initial=await page.evaluate(()=>({title:document.title,overflow:document.documentElement.scrollWidth>innerWidth,sections:document.querySelectorAll('section').length,sourceDrawers:document.querySelectorAll('.evidence').length,brokenAnchors:[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.querySelector(a.getAttribute('href'))).map(a=>a.href)}));
   await page.locator('.theme').click();
   if(!await page.locator('body').evaluate(e=>e.classList.contains('dark')))throw new Error('Theme switch failed');
   await page.locator('.theme').click();
   if(await page.locator('.flow-step').count()){
    const step=page.locator('.flow-step').first();await step.click();
    if(await step.getAttribute('aria-expanded')!=='false')throw new Error('Flow interaction failed');await step.click();
   }
   if(file==='modular-rag.html'){
    await page.locator('.rrf-demo input').nth(1).fill('0');
    if(await page.locator('.rrf-output').textContent()!=='0.016393')throw new Error('RRF output failed');
    await page.locator('.rrf-demo input').nth(1).fill('1');
   }
   if(file==='hp-optimization.html'){
    await page.locator('[data-filter=P0]').click();
    if(await page.locator('.priority:visible').count()!==7)throw new Error('P0 filter failed');
    await page.locator('[data-filter=ALL]').click();
    if(await page.locator('.priority:visible').count()!==13)throw new Error('All filter failed');
   }
   if(await page.locator('.evidence').count()){
    await page.locator('.evidence').first().locator('summary').click();
    if(!await page.locator('.evidence').first().getAttribute('open')&&await page.locator('.evidence').first().getAttribute('open')!== '')throw new Error('Evidence drawer failed');
   }
   await page.evaluate(()=>scrollTo(0,0));
   await page.screenshot({path:path.join(dir,`${file.replace('.html','')}-${width}.png`),fullPage:false});
   const brokenFiles=await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.getAttribute('href')).filter(h=>!h.startsWith('#')&&!h.startsWith('https:')));
   const missing=brokenFiles.filter(h=>!fs.existsSync(path.resolve(dir,decodeURIComponent(h))));
   results.push({file,width,...initial,errors,missingFiles:missing});
   if(initial.overflow||errors.length||missing.length||initial.brokenAnchors.length)throw new Error('QA failure '+JSON.stringify(results.at(-1)));
   await page.close();
  }
 }
 await browser.close();
 fs.writeFileSync(path.join(dir,'verification.json'),JSON.stringify(results,null,2));
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
