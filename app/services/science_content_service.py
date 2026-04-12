"""Science credibility content generation service.

Manages advisor spotlight posts, white paper excerpt generation,
dataset credibility posts, and peer review milestone content.
Feeds into the content writer agent with science-specific templates.

TODO: Implement advisor rotation, white paper excerpt extraction,
and peer review milestone campaign triggers.
"""


class ScienceContentService:
    """Placeholder for science credibility content pipeline."""

    def __init__(self, db):
        self.db = db

    def generate_advisor_spotlight(self, advisor_slug: str) -> dict:
        raise NotImplementedError("Science content service not yet implemented")

    def generate_white_paper_excerpt(self, paper_id: str) -> dict:
        raise NotImplementedError("Science content service not yet implemented")

    def generate_dataset_credibility_post(self) -> dict:
        raise NotImplementedError("Science content service not yet implemented")
