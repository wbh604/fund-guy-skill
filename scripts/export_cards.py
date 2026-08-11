"""导出传播卡片。参考实现,不是必须走的路。

用法:
    python scripts/export_cards.py reports/000000_20260630/report.html

Playwright 不可用时,直接在浏览器里按原尺寸截图也行 —— 产物一样。
"""
import asyncio
import sys
from pathlib import Path

CARDS = [
    ("#share-card", 1080, 1920, "share-card.png"),
    ("#war-report", 1920, 1080, "war-report.png"),
]


async def shoot(html: Path, out_dir: Path) -> list[Path]:
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for sel, w, h, name in CARDS:
            # 每张卡单独开 page:视口尺寸要和卡片一致,否则 fixed 定位会错位
            page = await browser.new_page(
                viewport={"width": w, "height": h}, device_scale_factor=2
            )
            await page.goto(html.resolve().as_uri())
            await page.evaluate("document.fonts.ready")

            node = page.locator(sel)
            if await node.count() == 0:
                print(f"  跳过 {name}:页面里没有 {sel}")
                await page.close()
                continue

            # 卡片默认藏在视口外,截图前挪进来
            await page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    const stage = el.closest('.card-stage') || el.parentElement;
                    Object.assign(stage.style,
                        {position:'static', left:'auto', transform:'none'});
                    Object.assign(el.style, {position:'static', left:'auto'});
                    window.scrollTo(0, 0);
                }""",
                sel,
            )
            await page.wait_for_timeout(260)  # 等条形图 transition 走完

            path = out_dir / name
            await node.screenshot(path=str(path))
            written.append(path)
            print(f"  ✓ {name}  {w}×{h} @2x")
            await page.close()

        await browser.close()
    return written


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    html = Path(sys.argv[1])
    if not html.exists():
        print(f"找不到 {html}")
        return 1

    out = Path(sys.argv[2]) if len(sys.argv) > 2 else html.parent
    print(f"导出分享图 → {out}")
    written = asyncio.run(shoot(html, out))
    print(f"完成,{len(written)} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
