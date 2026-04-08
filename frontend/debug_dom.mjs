import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => console.log(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message));
  
  await page.goto('http://localhost:5173', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000); // Wait 1 second
  
  const rootHtml = await page.$eval('#root', el => el.innerHTML);
  console.log('--- ROOT HTML ---');
  console.log(rootHtml);
  
  await browser.close();
})();
