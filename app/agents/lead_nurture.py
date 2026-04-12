from typing import Any


class LeadNurtureAgent:
    def recommend_touchpoint(self, lead: Any, examples: dict[str, Any]) -> dict[str, Any]:
        approved_examples = examples.get("approved_examples", [])
        stage = getattr(lead, "stage", "new")
        lead_name = getattr(lead, "name", "lead")

        if stage in {"qualified", "proposal"}:
            return {
                "touchpoint_type": "case-study-followup",
                "summary": f"Send a proof-led follow-up to {lead_name} using relevant client evidence.",
                "recommended_examples": approved_examples[:2],
            }

        return {
            "touchpoint_type": "awareness-touch",
            "summary": f"Keep {lead_name} warm with a thought-leadership touchpoint.",
            "recommended_examples": approved_examples[:2],
        }
