from typing import Any


class CompetitorScoutAgent:
    def classify_observation(self, payload: dict[str, Any]) -> dict[str, str]:
        headline = (payload.get("headline") or payload.get("summary") or "").strip()
        content = " ".join(
            filter(
                None,
                [
                    headline,
                    str(payload.get("summary") or ""),
                    str(payload.get("body") or ""),
                ],
            )
        ).lower()

        signal_type = "general_update"
        severity = "low"
        reaction_angle = "Track the signal and decide whether a proof-led response is worth drafting."

        if any(term in content for term in ["pressure", "mental", "mindset", "resilience"]):
            signal_type = "positioning_shift"
            severity = "medium"
            reaction_angle = "Answer with proof-first coach credibility rather than copying the claim."
        elif any(term in content for term in ["launch", "rollout", "announce", "partnership"]):
            signal_type = "market_launch"
            severity = "medium"
            reaction_angle = "Frame the market change through NTangible's established operating system."
        elif any(term in content for term in ["pricing", "discount", "free"]):
            signal_type = "pricing_move"
            severity = "high"
            reaction_angle = "Reinforce differentiation around outcomes, not price."

        return {
            "signal_type": signal_type,
            "summary": headline or payload.get("summary") or "Competitor update captured",
            "severity": severity,
            "reaction_angle": reaction_angle,
        }
