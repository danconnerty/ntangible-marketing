from app.models.campaign import Campaign
from app.models.workflow import Workflow


class CampaignPlannerAgent:
    def build_manual_request(self, campaign: Campaign, workflow: Workflow) -> str:
        parts = [
            f"Campaign: {campaign.name} ({campaign.slug})",
            f"Objective: {campaign.objective}",
            f"Audience: {campaign.audience}",
            f"Theme: {campaign.theme}",
            f"Workflow: {workflow.name} ({workflow.platform.value})",
            f"Content type: {workflow.content_type}",
            "Create one campaign-aligned draft that advances this campaign objective for the mapped workflow.",
        ]
        return "\n".join(parts)
