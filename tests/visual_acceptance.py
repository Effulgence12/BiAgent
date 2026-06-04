"""Browser-level visual acceptance for the Olist Agentic BI dashboard.

This script intentionally uses the system Edge browser instead of running
``playwright install`` so it does not download Playwright-managed Chromium.
It is a manual acceptance helper, not part of the default pytest suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import argparse
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
SCREENSHOT_DIR = ROOT / "docs" / "screenshots" / "visual_acceptance"
BASE_URL = os.environ.get("VISUAL_ACCEPTANCE_BASE_URL", "http://127.0.0.1:8000")
PYTHON = Path(sys.executable)


@dataclass(frozen=True)
class Scenario:
    name: str
    question: str
    expect_chart_text: str = ""


SCENARIOS = [
    Scenario("01_gmv_trend", "2017年各月GMV趋势？", "数据表"),
    Scenario("02_delivery_map", "地图中显示延迟配送最严重的州", "数据表"),
    Scenario("03_payment_heatmap", "不同支付方式和分期数的订单分布热力图应该怎么看？", "数据表"),
    Scenario("04_forecast", "未来6周GMV预测是多少？需要置信区间和误差说明。", "数据表"),
    Scenario("05_followup", "继续分析刚才图表中最需要关注的区域。", "数据表"),
]


def _wait_for_server() -> None:
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            with urlopen(f"{BASE_URL}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.8)
    raise RuntimeError("FastAPI server did not become ready within 45 seconds")


def _start_server() -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_for_server()
    return process


def _submit_question(page: Page, scenario: Scenario, viewport_name: str) -> dict[str, object]:
    page.fill("#question", scenario.question)
    page.click("#question-form button[type='submit']")

    try:
        page.wait_for_function(
            "() => { const text = document.querySelector('#stage-label')?.textContent || ''; return text.includes('完成') || text.includes('失败'); }",
            timeout=240_000,
        )
    except PlaywrightTimeoutError as exc:
        fail_path = SCREENSHOT_DIR / f"{viewport_name}_{scenario.name}_timeout.png"
        page.screenshot(path=str(fail_path), full_page=True)
        stage = page.locator("#stage-label").inner_text(timeout=5_000)
        raw = page.locator("#raw-output").inner_text(timeout=5_000)
        raise AssertionError(f"{scenario.name} did not complete in {viewport_name}; stage={stage}; screenshot={fail_path}; raw={raw[-1200:]}") from exc

    stage_text = page.locator("#stage-label").inner_text(timeout=5_000)
    if "失败" in stage_text:
        fail_path = SCREENSHOT_DIR / f"{viewport_name}_{scenario.name}_failed.png"
        page.screenshot(path=str(fail_path), full_page=True)
        raw = page.locator("#raw-output").inner_text(timeout=5_000)
        raise AssertionError(f"{scenario.name} failed in {viewport_name}; screenshot={fail_path}; raw={raw[-1200:]}")

    chart_text = page.locator("#chart-stage").inner_text(timeout=10_000)
    advice_text = page.locator("#advice-stream").inner_text(timeout=10_000)
    agent_text = page.locator("#agent-events").inner_text(timeout=10_000)
    direct_answer = page.locator("#direct-answer").inner_text(timeout=10_000)
    data_table_count = page.locator("#chart-stage .data-table").count()
    chart_buttons = page.locator("#chart-list .chart-button").count()

    if scenario.expect_chart_text and scenario.expect_chart_text not in chart_text:
        raise AssertionError(f"{scenario.name} chart evidence table missing in {viewport_name}")
    if not direct_answer.strip() or "等待" in direct_answer:
        raise AssertionError(f"{scenario.name} direct answer missing in {viewport_name}")
    if not advice_text.strip() or "等待真实大模型" in advice_text:
        raise AssertionError(f"{scenario.name} LLM advice did not stream in {viewport_name}")
    if "生成 SQL 任务" not in agent_text or "流程完成" not in agent_text:
        raise AssertionError(f"{scenario.name} agent events incomplete in {viewport_name}")
    if data_table_count < 1:
        raise AssertionError(f"{scenario.name} has chart but no evidence table in {viewport_name}")

    page.click(".tab[data-target='chart']")
    page.wait_for_function(
        "() => document.querySelector('#chart')?.classList.contains('active')",
        timeout=10_000,
    )
    page.wait_for_timeout(2_000)
    path = SCREENSHOT_DIR / f"{viewport_name}_{scenario.name}_chart.png"
    page.screenshot(path=str(path), full_page=True)
    return {
        "scenario": scenario.name,
        "question": scenario.question,
        "viewport": viewport_name,
        "screenshot": str(path.relative_to(ROOT)),
        "chart_buttons": chart_buttons,
        "data_tables": data_table_count,
        "direct_answer": direct_answer,
        "advice_chars": len(advice_text),
    }


def _run_viewport(browser, viewport_name: str, width: int, height: int, scenarios: list[Scenario]) -> list[dict[str, object]]:
    context = browser.new_context(viewport={"width": width, "height": height}, locale="zh-CN")
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#question", timeout=20_000)
    results = []
    for scenario in scenarios:
        results.append(_submit_question(page, scenario, viewport_name))
    context.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run browser-level visual acceptance against the local dashboard.")
    parser.add_argument("--include-mobile", action="store_true", help="Also run a lightweight narrow-screen check.")
    parser.add_argument("--scenario", action="append", help="Run only the named scenario. Can be passed more than once.")
    args = parser.parse_args()

    if not EDGE_PATH.exists():
        raise SystemExit(f"System Edge not found: {EDGE_PATH}")
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = SCENARIOS
    if args.scenario:
        requested = set(args.scenario)
        scenarios = [scenario for scenario in SCENARIOS if scenario.name in requested]
        missing = requested - {scenario.name for scenario in scenarios}
        if missing:
            raise SystemExit(f"Unknown visual acceptance scenario(s): {', '.join(sorted(missing))}")

    server = _start_server()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(EDGE_PATH), headless=True)
            results = []
            results.extend(_run_viewport(browser, "desktop", 1440, 900, scenarios))
            if args.include_mobile:
                # 答辩以 PC Web 为主；窄屏检查作为可选轻量项，避免额外消耗模型额度。
                results.extend(_run_viewport(browser, "mobile", 390, 844, scenarios[:1]))
            browser.close()
        report_path = SCREENSHOT_DIR / "visual_acceptance_report.json"
        report_path.write_text(json.dumps({"passed": True, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"passed": True, "report": str(report_path.relative_to(ROOT)), "results": results}, ensure_ascii=False, indent=2))
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
