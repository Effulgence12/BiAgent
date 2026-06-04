"""DecisionMaker agent for actionable Olist operations recommendations."""

from __future__ import annotations

from config.prompts import DECISION_MAKER_SYSTEM_PROMPT
from utils.llm_client import chat_completion


def _parse_recommendations(text: str) -> list[str]:
    """Convert a compact LLM answer into three recommendation bullets."""
    lines = [line.strip(" -\t0123456789.、") for line in text.splitlines() if line.strip()]
    cleaned = [line for line in lines if len(line) >= 8]
    if len(cleaned) >= 3:
        return cleaned[:3]
    if text.strip():
        return [text.strip()]
    return []


def build_recommendation_prompt(
    analysis_type: str,
    summary: str,
    question: str = "",
    direct_answer: str = "",
    rows: list[dict[str, object]] | None = None,
) -> str:
    """Build a readable, data-grounded recommendation prompt."""
    rows = rows or []
    return (
        f"用户问题：{question}\n"
        f"分析类型：{analysis_type}\n"
        f"直接数据答案：{direct_answer}\n"
        f"数据摘要：{summary}\n"
        f"样例数据前三行：{rows[:3]}\n\n"
        "请严格围绕用户问题输出，不能扩展到无关州、无关月份或无关品类。\n"
        "输出格式：\n"
        "1. 先用1句话直接回答问题，语言要像业务汇报，不要堆字段名。\n"
        "2. 再给3条建议，每条建议用自然中文写成1到2句话，约120到180字。\n"
        "3. 每条建议要说清楚：应该做什么、为什么现在该做、做完后业务上会改善什么。\n"
        "4. 不要使用“问题定位：”“根因：”“行动：”“预期效果：”这类固定标签。\n"
        "5. 只使用上面的真实数据，不要编造数字，不要输出推理过程。"
    )


def build_recommendations(
    analysis_type: str,
    rows: list[dict[str, object]] | None = None,
    summary: str = "",
    question: str = "",
    direct_answer: str = "",
) -> list[str]:
    """Return data-aware recommendations from the configured remote LLM.

    决策建议属于作业要求中的大模型能力。这里不再提供本地规则建议，
    以免 API Key 失效时仍让页面看起来“正常完成”。
    """
    prompt = build_recommendation_prompt(analysis_type, summary, question, direct_answer, rows)
    llm_response = chat_completion(DECISION_MAKER_SYSTEM_PROMPT, prompt, max_tokens=1100)
    parsed = _parse_recommendations(llm_response.content)
    if not parsed:
        raise RuntimeError("LLM returned an empty recommendation response")
    return parsed
