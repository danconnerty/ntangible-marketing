from __future__ import annotations

from typing import Any


class VideoWriterAgent:
    def build_brief(
        self,
        *,
        kind: str,
        target_platform: str,
        context: str | None = None,
        source_mode: str = "manual",
        title: str | None = None,
        audience: str | None = None,
        cta: str | None = None,
        source_material: str | None = None,
    ) -> dict[str, Any]:
        platform = target_platform.lower()
        kind = kind.lower()
        focus = (context or source_material or title or audience or "the core NTangible narrative").strip()
        title = title or self._default_title(kind, platform, focus)
        hook = self._build_hook(kind, platform, focus)
        thesis = self._build_thesis(kind, platform, focus)
        script = self._build_script(kind, platform, focus, hook, thesis, cta)
        shot_list = self._build_shot_list(kind, platform, focus)
        motion_graphic_notes = self._build_motion_graphic_notes(kind, platform, focus)
        caption = self._build_caption(kind, platform, focus)
        cta = cta or self._default_cta(kind, platform)
        duration = 20 if kind == "reel_from_static" else 35 if kind == "testimonial" else 45

        return {
            "title": title,
            "kind": kind,
            "target_platform": platform,
            "brief_format": self._brief_format(kind),
            "source_mode": source_mode,
            "focus": focus,
            "hook": hook,
            "thesis": thesis,
            "script": script,
            "shot_list": shot_list,
            "motion_graphic_notes": motion_graphic_notes,
            "caption": caption,
            "cta": cta,
            "estimated_duration_seconds": duration,
            "request_text": self._request_text(kind, platform, title, focus, source_mode),
            "source_context": {
                "context": context,
                "source_material": source_material,
                "audience": audience,
                "source_mode": source_mode,
            },
        }

    def build_testimonial_request(
        self,
        *,
        athlete_name: str,
        score: int,
        score_tier: str,
        parent_name: str | None = None,
        athlete_email: str | None = None,
        parent_email: str | None = None,
        sport: str | None = None,
    ) -> dict[str, Any]:
        subject = f"{athlete_name}, share your clutch story"
        preview_text = (
            f"Your {score_tier} result opens the door to a short testimonial video."
        )
        lines = [
            f"Hi {athlete_name},",
            "",
            f"Your Clutch Factor score of {score} means it's a great time to capture a short testimonial.",
            "Reply with a 15-30 second selfie video answering:",
            "\"How do you view yourself in clutch situations?\"",
            "",
            "We will only share it with consent.",
        ]
        if parent_name:
            lines.append(f"Copy your parent/guardian here: {parent_name}.")
        if sport:
            lines.append(f"Sport: {sport}")
        request_copy = "\n".join(lines)
        return {
            "subject": subject,
            "preview_text": preview_text,
            "request_copy": request_copy,
            "athlete_name": athlete_name,
            "athlete_email": athlete_email,
            "parent_name": parent_name,
            "parent_email": parent_email,
            "score": score,
            "score_tier": score_tier,
            "sport": sport,
        }

    def _brief_format(self, kind: str) -> str:
        if kind == "reel_from_static":
            return "reel"
        if kind == "testimonial":
            return "testimonial_video"
        if kind == "partner_cutdown":
            return "partner_cutdown"
        return "founder_raw"

    def _default_title(self, kind: str, platform: str, focus: str) -> str:
        if kind == "reel_from_static":
            return f"Reel brief for {platform}: {focus[:48]}"
        if kind == "testimonial":
            return f"Testimonial video brief: {focus[:48]}"
        if kind == "partner_cutdown":
            return f"Partner cutdown brief: {focus[:48]}"
        return f"Founder video brief: {focus[:48]}"

    def _default_cta(self, kind: str, platform: str) -> str:
        if kind == "reel_from_static":
            return "Follow for the full breakdown."
        if kind == "testimonial":
            return "Watch the full testimonial."
        if kind == "partner_cutdown":
            return "See the partner recap."
        if platform == "linkedin":
            return "Thoughts?"
        return "Want the full story?"

    def _build_hook(self, kind: str, platform: str, focus: str) -> str:
        if kind == "reel_from_static":
            return f"Turn this proof into a {platform} reel that stops the scroll."
        if kind == "testimonial":
            return f"Lead with the athlete voice, not the marketing voice."
        if kind == "partner_cutdown":
            return f"Show the partner win in one sharp opening beat."
        return f"Open with the core point around {focus}."

    def _build_thesis(self, kind: str, platform: str, focus: str) -> str:
        if kind == "reel_from_static":
            return "A static proof point can become a short, high-retention reel with kinetic text."
        if kind == "testimonial":
            return "A consented athlete story becomes a credibility asset across channels."
        if kind == "partner_cutdown":
            return "Partner proof should feel useful, specific, and easy to repurpose."
        return "Founder-facing raw video should sound like a direct explanation from the arena."

    def _build_script(self, kind: str, platform: str, focus: str, hook: str, thesis: str, cta: str | None) -> str:
        if kind == "reel_from_static":
            return "\n".join(
                [
                    f"Hook: {hook}",
                    f"Proof: {thesis}",
                    f"Overlay: {focus}",
                    f"CTA: {cta or self._default_cta(kind, platform)}",
                ]
            )
        if kind == "testimonial":
            return "\n".join(
                [
                    f"Hook: {hook}",
                    "Prompt the athlete to describe what pressure feels like in one sentence.",
                    "Follow with a concrete example from training or competition.",
                    f"CTA: {cta or self._default_cta(kind, platform)}",
                ]
            )
        if kind == "partner_cutdown":
            return "\n".join(
                [
                    f"Hook: {hook}",
                    "Cut to the strongest partner proof line.",
                    "Keep the edit tight and remove anything that slows the clip down.",
                    f"CTA: {cta or self._default_cta(kind, platform)}",
                ]
            )
        return "\n".join(
            [
                f"Hook: {hook}",
                "Talk through the point in a direct founder voice.",
                "Use one proof point and one specific takeaway.",
                f"CTA: {cta or self._default_cta(kind, platform)}",
            ]
        )

    def _build_shot_list(self, kind: str, platform: str, focus: str) -> list[str]:
        if kind == "reel_from_static":
            return [
                "Title card with kinetic text",
                f"Zoom on the strongest line from: {focus}",
                "Cutaway to the stat or visual proof",
                "End card with CTA",
            ]
        if kind == "testimonial":
            return [
                "Open with the athlete on camera",
                "Insert lower-third identification",
                "Use a close-up for the key line",
                "Close on consent-safe call to action",
            ]
        if kind == "partner_cutdown":
            return [
                "Partner logo bumper",
                "Best proof moment",
                "Secondary supporting stat",
                "Recap card with CTA",
            ]
        return [
            "Opening direct-to-camera hook",
            "B-roll of the product or proof point",
            "One data-backed supporting beat",
            "Closing line and CTA",
        ]

    def _build_motion_graphic_notes(self, kind: str, platform: str, focus: str) -> str | None:
        if kind != "reel_from_static":
            return "Keep cuts simple and let the speaking track carry the clip."
        return (
            "Convert the static proof into kinetic text, animated stat callouts, and a fast title card. "
            f"Use the strongest line from: {focus}."
        )

    def _build_caption(self, kind: str, platform: str, focus: str) -> str:
        if kind == "reel_from_static":
            return f"Reel brief built from static proof: {focus}"
        if kind == "testimonial":
            return f"Athlete testimonial concept centered on {focus}"
        if kind == "partner_cutdown":
            return f"Partner cutdown concept around {focus}"
        return f"Founder raw video concept around {focus}"

    def _request_text(self, kind: str, platform: str, title: str, focus: str, source_mode: str) -> str:
        return "\n".join(
            [
                f"Video brief kind: {kind}",
                f"Target platform: {platform}",
                f"Source mode: {source_mode}",
                f"Title: {title}",
                f"Focus: {focus}",
                "Return a short, usable brief that can be reviewed and turned into a real draft later.",
            ]
        )
