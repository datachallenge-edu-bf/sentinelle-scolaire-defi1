import asyncio, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width":1536,"height":1000}, device_scale_factor=1)
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto("file:///home/claude/sentinelle/web/sentinelle_scolaire.html")
        await pg.wait_for_timeout(500)
        await pg.screenshot(path="s_nat.png", full_page=True)
        for v in ["territoire","eleves","alertes","assistant"]:
            await pg.click(f".tabs [data-go={v}]" if v!="alertes" else ".bell")
            if v=="assistant":
                await pg.click("#chips button:nth-child(2)"); await pg.wait_for_timeout(400)
                await pg.click("#chips button:nth-child(5)"); await pg.wait_for_timeout(400)
            await pg.screenshot(path=f"s_{v}.png", full_page=True)
        m = await b.new_page(viewport={"width":390,"height":844}, device_scale_factor=1)
        await m.goto("file:///home/claude/sentinelle/web/sentinelle_scolaire.html"); await m.wait_for_timeout(400)
        await m.screenshot(path="s_mobile.png", full_page=False)
        print("errors:", errs)
        await b.close()
asyncio.run(main())
