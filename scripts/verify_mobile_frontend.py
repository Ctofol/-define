from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import websocket


DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
VIEWPORTS = [(360, 800), (390, 844), (400, 739), (430, 932)]
PAGES = [
    ("首页", "overview"),
    ("识别", "animal"),
    ("动物", "animalKnowledge"),
    ("植物", "plantKnowledge"),
    ("记录", "records"),
]


class DevTools:
    def __init__(self, websocket_url: str) -> None:
        self.socket = websocket.create_connection(websocket_url, timeout=10)
        self.sequence = 0

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sequence += 1
        message_id = self.sequence
        self.socket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.socket.recv())
            if response.get("id") == message_id:
                if "error" in response:
                    raise RuntimeError(f"{method}: {response['error']}")
                return response.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        return result["result"].get("value")

    def close(self) -> None:
        self.socket.close()


def wait_for_debugger(port: int, timeout: float = 15) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                targets = json.load(response)
            page = next((target for target in targets if target.get("type") == "page"), None)
            if page:
                return str(page["webSocketDebuggerUrl"])
        except (OSError, ValueError):
            time.sleep(0.2)
    raise RuntimeError("Chrome 调试端口启动超时")


def wait_for(client: DevTools, expression: str, timeout: float = 12) -> Any:
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = client.evaluate(expression)
        if value:
            return value
        time.sleep(0.2)
    raise RuntimeError(f"页面等待超时：{expression}")


def capture(client: DevTools, path: Path) -> None:
    payload = client.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    path.write_bytes(base64.b64decode(payload["data"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="用真实 Chrome 手机视口验收森智眼移动端核心页面。")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    parser.add_argument("--output", type=Path, default=Path("tmp/mobile-qa"))
    parser.add_argument("--debug-port", type=int, default=9333)
    args = parser.parse_args()

    if not args.chrome.exists():
        raise SystemExit(f"未找到 Chrome：{args.chrome}")
    args.output.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="wildlife-mobile-qa-") as profile:
        chrome = subprocess.Popen(
            [
                str(args.chrome),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-allow-origins=*",
                f"--remote-debugging-port={args.debug_port}",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        client: DevTools | None = None
        try:
            client = DevTools(wait_for_debugger(args.debug_port))
            client.call("Page.enable")
            client.call("Runtime.enable")

            for width, height in VIEWPORTS:
                client.call(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": True},
                )
                client.call("Page.navigate", {"url": args.base_url})
                wait_for(client, "document.readyState === 'complete'")
                client.evaluate(
                    "localStorage.removeItem('wildlife-demo-auth');"
                    "localStorage.removeItem('wildlife-demo-account'); location.reload(); true"
                )
                wait_for(client, "Boolean(document.querySelector('.login-submit'))")
                login_metrics = client.evaluate(
                    "(() => { const image=document.querySelector('.login-image-board')?.getBoundingClientRect();"
                    "const title=document.querySelector('.login-title-block')?.getBoundingClientRect();"
                    "return {viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,"
                    "buttonVisible:Boolean(document.querySelector('.login-submit')?.offsetParent),"
                    "imageBottom:image?.bottom ?? 0,titleTop:title?.top ?? 0,"
                    "titleOverlapsImage:Boolean(image && title && title.top < image.bottom + 8)}; })()"
                )
                results.append({"width": width, "height": height, "page": "login", **login_metrics})
                if login_metrics["documentWidth"] > login_metrics["viewport"] or not login_metrics["buttonVisible"]:
                    failures.append(f"{width}px/登录：入口不可见或页面横向溢出")
                if login_metrics["titleOverlapsImage"]:
                    failures.append(f"{width}px/登录：品牌标题与头图发生重叠")
                if width in {390, 400}:
                    capture(client, args.output / f"login-{width}x{height}.png")
                client.evaluate("document.querySelector('.login-submit').click(); true")
                wait_for(client, "document.querySelectorAll('.mobile-navigation button').length === 5")
                if "首页" not in str(client.evaluate("document.querySelector('.mobile-navigation button[aria-current=page]')?.textContent || ''")):
                    failures.append(f"{width}px/登录：进入系统后未落到移动首页")
                time.sleep(1.5)

                for label, page_name in PAGES:
                    clicked = client.evaluate(
                        "(() => { const b=[...document.querySelectorAll('.mobile-navigation button')]"
                        f".find(x=>x.textContent.includes({json.dumps(label, ensure_ascii=False)}));"
                        "if(!b)return false;b.click();return true;})()"
                    )
                    if not clicked:
                        failures.append(f"{width}px：找不到“{label}”导航")
                        continue
                    wait_for(client, f"Boolean(document.querySelector('.page-{page_name}'))")
                    if page_name in {"animalKnowledge", "plantKnowledge"}:
                        wait_for(client, "Boolean(document.querySelector('.knowledge-card'))", timeout=45)
                    if page_name == "plantKnowledge":
                        wait_for(
                            client,
                            "(() => { const imgs=[...document.querySelectorAll('.knowledge-card-image img')].slice(0,2);"
                            "return imgs.length > 0 && imgs.every(img => img.complete && img.naturalWidth > 0); })()",
                            timeout=60,
                        )
                    time.sleep(0.35)
                    metrics = client.evaluate(
                        "(() => ({"
                        "viewport: innerWidth,"
                        "documentWidth: document.documentElement.scrollWidth,"
                        "headerVisible: getComputedStyle(document.querySelector('.mobile-header')).display !== 'none',"
                        "navItems: document.querySelectorAll('.mobile-navigation button').length,"
                        "activeNav: document.querySelector('.mobile-navigation button[aria-current=page]')?.textContent.trim() || '',"
                        "metrics: document.querySelectorAll('.metric-card').length,"
                        "modules: document.querySelectorAll('.module-card').length,"
                        "cards: document.querySelectorAll('.knowledge-card').length,"
                        "images: document.querySelectorAll('.knowledge-card-image img').length,"
                        "loadedImages: [...document.querySelectorAll('.knowledge-card-image img')]"
                        ".filter(img => img.complete && img.naturalWidth > 0).length"
                        "}))()"
                    )
                    result = {"width": width, "height": height, "page": page_name, **metrics}
                    results.append(result)
                    if metrics["documentWidth"] > metrics["viewport"]:
                        failures.append(f"{width}px/{label}：页面横向溢出 {metrics['documentWidth'] - metrics['viewport']}px")
                    if not metrics["headerVisible"] or metrics["navItems"] != 5:
                        failures.append(f"{width}px/{label}：移动导航结构不完整")
                    if page_name == "overview" and (metrics["metrics"] < 4 or metrics["modules"] < 5):
                        failures.append(f"{width}px/首页：统计卡或功能入口未渲染")
                    if page_name == "plantKnowledge" and (metrics["cards"] < 1 or metrics["images"] != metrics["cards"]):
                        failures.append(f"{width}px/植物：知识卡或封面未完整渲染")
                    if page_name == "plantKnowledge" and metrics["loadedImages"] < 1:
                        failures.append(f"{width}px/植物：首屏封面图片未成功加载")
                    if width == 390:
                        capture(client, args.output / f"{page_name}-{width}x{height}.png")

                client.evaluate(
                    "[...document.querySelectorAll('.mobile-navigation button')]"
                    ".find(x=>x.textContent.includes('植物'))?.click(); true"
                )
                wait_for(client, "Boolean(document.querySelector('.page-plantKnowledge .knowledge-card'))")
                client.evaluate("document.querySelector('.page-plantKnowledge .knowledge-card').click(); true")
                wait_for(client, "Boolean(document.querySelector('.knowledge-modal'))")
                wait_for(
                    client,
                    "(() => { const img=document.querySelector('.knowledge-modal .knowledge-plant-hero img');"
                    "return Boolean(img && img.complete && img.naturalWidth > 0); })()",
                    timeout=60,
                )
                modal = client.evaluate(
                    "(() => { const m=document.querySelector('.knowledge-modal'); const r=m.getBoundingClientRect();"
                    "return {width:r.width,height:r.height,scrollHeight:m.scrollHeight,plantImage:Boolean(m.querySelector('.knowledge-plant-hero img'))}; })()"
                )
                if modal["width"] > width + 1 or modal["height"] > height + 1 or not modal["plantImage"]:
                    failures.append(f"{width}px/植物详情：弹层尺寸或头图异常")
                if width == 390:
                    capture(client, args.output / f"plant-detail-{width}x{height}.png")
                client.evaluate("document.querySelector('.knowledge-modal .icon-close')?.click(); true")
        finally:
            if client:
                client.close()
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()

    report = {"base_url": args.base_url, "viewports": VIEWPORTS, "checks": results, "failures": failures}
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": len(results), "failures": failures, "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
