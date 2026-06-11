import json
import os
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv


load_dotenv()


class AiAnalyzerError(Exception):
    """Raised when AI analysis cannot be completed."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def analyze_costs(scan_result: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AiAnalyzerError(
            "GEMINI_API_KEY is not set. Add it to your environment or .env file.",
            status_code=503,
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )

    prompt = _build_prompt(scan_result)

    try:
        response = model.generate_content(prompt)
    except Exception as exc:
        raise AiAnalyzerError(f"Gemini API request failed: {exc}", status_code=502) from exc

    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise AiAnalyzerError("Gemini API returned an empty analysis.", status_code=502)

    try:
        analysis = json.loads(_strip_json_fence(text))
    except json.JSONDecodeError as exc:
        raise AiAnalyzerError("Gemini API returned invalid JSON analysis.", status_code=502) from exc

    return _normalize_analysis(analysis)


def _build_prompt(scan_result: dict[str, Any]) -> str:
    resources_json = json.dumps(scan_result, indent=2, default=str)

    return f"""
You are an AWS cloud cost optimization analyst.

Analyze this AWS resource inventory for cost risks and optimization opportunities:

{resources_json}

Look specifically for:
- Over-provisioned EC2 instances: wrong instance family, oversized CPU/RAM, missing Graviton migration.
- Unused resources: unattached EBS volumes, idle Elastic IPs, unused ELBs/ALBs, orphaned snapshots.
- Misconfigurations: On-Demand usage where Savings Plans or Reserved Instances may fit, missing auto-shutdown, no spot usage.
- Storage and logging costs: S3 storage without lifecycle policies, excessive CloudWatch Logs retention, unused RDS instances.

Return only valid JSON with this exact shape:
{{
  "summary": "Short plain-English summary of the cost posture.",
  "estimated_monthly_savings": "Estimated savings as a string. Use 'unknown' if there is not enough data.",
  "issues": [
    {{
      "title": "Issue title",
      "severity": "high|medium|low",
      "resource": "Resource ARN or identifier",
      "finding": "What is wrong or risky.",
      "estimated_monthly_savings": "Estimated monthly savings for this issue, or unknown.",
      "recommendation": "What the user should do.",
      "fix_commands": ["AWS CLI command the user can run"]
    }}
  ],
  "next_steps": ["Prioritized action item"]
}}

Rules:
- Do not invent resources that are not present in the inventory.
- If utilization metrics are missing, say that metrics are needed before rightsizing and suggest AWS CLI or CloudWatch checks.
- Use AWS CLI commands only in fix_commands.
- Keep commands cautious. Prefer read-only validation commands unless the fix is obvious.
""".strip()


def _strip_json_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    return text


def _normalize_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    issues = analysis.get("issues")
    if not isinstance(issues, list):
        issues = []

    normalized_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue

        severity = str(issue.get("severity", "low")).lower()
        if severity not in {"high", "medium", "low"}:
            severity = "low"

        fix_commands = issue.get("fix_commands", [])
        if not isinstance(fix_commands, list):
            fix_commands = []

        normalized_issues.append(
            {
                "title": str(issue.get("title", "Cost optimization issue")),
                "severity": severity,
                "resource": str(issue.get("resource", "")),
                "finding": str(issue.get("finding", "")),
                "estimated_monthly_savings": str(issue.get("estimated_monthly_savings", "unknown")),
                "recommendation": str(issue.get("recommendation", "")),
                "fix_commands": [str(command) for command in fix_commands],
            }
        )

    next_steps = analysis.get("next_steps", [])
    if not isinstance(next_steps, list):
        next_steps = []

    return {
        "summary": str(analysis.get("summary", "")),
        "estimated_monthly_savings": str(analysis.get("estimated_monthly_savings", "unknown")),
        "issues": normalized_issues,
        "next_steps": [str(step) for step in next_steps],
    }
