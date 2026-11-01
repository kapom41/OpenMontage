"""Hook & Script Agent — generates 5 hooks from 21 formulas, scores them, writes full retention-optimized script.

Integrates youtube-agent-skill's 21 hook formulas and hook scoring with OpenMontage's
ScriptWriterAgent for cinematic narrative structure.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.viral_pattern import HOOK_FORMULAS, HookScorer
from lib.creative_director import CreativeDirection, SceneConcept
from lib.script_writer import ScriptWriterAgent, Script, ScriptSection


@dataclass
class HookOption:
    """A single hook option with scoring."""
    text: str
    formula_id: str
    formula_name: str
    score: int
    band: str
    properties: dict[str, int]
    matched_patterns: int
    weakest_property: str
    weakest_fix: str


@dataclass
class HookScriptResult:
    """Complete result: top hooks + full script."""
    topic: str
    hook_options: list[HookOption]
    winning_hook: HookOption
    script: Script
    runtime_estimate_minutes: float
    formula_rationale: str
    generated_at: str


class HookScriptAgent:
    """Generates 5 hooks from 21 formulas, scores them, and writes the full script."""

    PACING_WPS = {
        "slow": 2.0,
        "measured": 2.5,
        "conversational": 3.0,
        "brisk": 3.5,
        "fast": 4.0,
    }

    def __init__(self):
        self.script_writer = ScriptWriterAgent()
        self.hook_scorer = HookScorer()

    def generate(
        self,
        direction: CreativeDirection,
        language: str = "en",
        num_hook_options: int = 5,
    ) -> HookScriptResult:
        """Generate hook options, pick winner, write full script."""

        # Generate 5 hook options from different formulas
        hook_options = self._generate_hook_options(direction, num_hook_options)

        # Score all hooks
        scored_hooks = []
        for hook in hook_options:
            score_result = self.hook_scorer.score(hook.text)
            scored_hooks.append(HookOption(
                text=hook.text,
                formula_id=hook.formula_id,
                formula_name=hook.formula_name,
                score=score_result["verdict"],
                band=score_result["band"],
                properties=score_result["properties"],
                matched_patterns=score_result["matched_patterns"],
                weakest_property=score_result["weakest"],
                weakest_fix=self._get_fix(score_result["weakest"]),
            ))

        # Sort by score, keep top 2
        scored_hooks.sort(key=lambda h: -h.score)
        top_hooks = scored_hooks[:2]
        winner = top_hooks[0]

        # Update direction with winning hook
        direction.hook = winner.text

        # Write full script using ScriptWriterAgent
        script = self.script_writer.write_script(direction, language)

        # Calculate runtime
        word_count = sum(len(s.text.split()) for s in script.sections)
        runtime = word_count / 150.0  # 150 wpm

        # Formula rationale
        formula_rationale = self._get_formula_rationale(winner, direction)

        return HookScriptResult(
            topic=direction.title,
            hook_options=scored_hooks,
            winning_hook=winner,
            script=script,
            runtime_estimate_minutes=round(runtime, 1),
            formula_rationale=formula_rationale,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _generate_hook_options(
        self,
        direction: CreativeDirection,
        num_options: int,
    ) -> list[HookOption]:
        """Generate hook options using different formulas."""
        topic = direction.title.split(":")[0] if ":" in direction.title else direction.title
        core = direction.core_concept

        # Select diverse formulas based on viral pattern recommendations
        recommended = direction.narrative_arc[:3] if direction.narrative_arc else ["establish", "conflict", "revelation"]

        formula_map = {
            "establish": ["the-statistic", "the-origin", "the-list"],
            "conflict": ["the-mistake", "contrarian-flip", "the-warning"],
            "revelation": ["the-reveal", "the-teardown", "the-receipt"],
            "mystery": ["the-question", "the-insider", "the-impossible"],
            "before_state": ["the-before-after", "the-superlative", "the-comparison"],
            "catalyst": ["the-clock", "i-tried-it", "someone-elses-result"],
            "inciting_incident": ["the-question", "the-mistake", "the-impossible"],
            "problem": ["the-mistake", "the-warning", "the-question"],
        }

        selected_formulas = []
        for beat in recommended:
            if beat in formula_map:
                selected_formulas.extend(formula_map[beat])
        # Add universally good formulas
        selected_formulas.extend(["the-statistic", "the-reveal", "the-question", "contrarian-flip", "the-mistake"])
        selected_formulas = list(dict.fromkeys(selected_formulas))[:num_options]

        hooks = []
        for fid in selected_formulas:
            formula = next((f for f in HOOK_FORMULAS if f["id"] == fid), None)
            if not formula:
                continue

            hook_text = self._craft_hook(formula, topic, core, direction)
            hooks.append(HookOption(
                text=hook_text,
                formula_id=fid,
                formula_name=formula["name"],
                score=0,  # Will be scored later
                band="",
                properties={},
                matched_patterns=0,
                weakest_property="",
                weakest_fix="",
            ))

        return hooks

    def _craft_hook(self, formula: dict, topic: str, core: str, direction: CreativeDirection) -> str:
        """Craft a hook using a specific formula."""
        templates = {
            "the-statistic": f"{{stat}}% of {{topic}} {{consequence}}. Here is what the {{percentile}}% do differently.",
            "someone-elses-result": f"This {{entity}} went from {{from_state}} to {{to_state}} in {{timeframe}}. I mapped it.",
            "the-mistake": f"Your {{mistake_area}} is why {{negative_outcome}}. It is not the {{not_this}}.",
            "contrarian-flip": f"Everyone says {{accepted_advice}}. I {{contrarian_action}} and {{result}}.",
            "the-reveal": f"I am going to show you the exact {{artifact}} that {{outcome}}.",
            "the-superlative": f"This is the {{superlative}} way to {{achieve_outcome}}.",
            "the-clock": f"In the next {{timeframe}} you will {{deliverable}}.",
            "i-tried-it": f"I {{experiment}} for {{duration}}. {{benefit}}.",
            "the-question": f"{{question}}",
            "the-before-after": f"This was {{before}}. This is {{after}}. Same {{subject}}, {{multiple}}x the {{result}}.",
            "the-teardown": f"I pulled the {{number}} most-{{category}} {{topic}} and broke down what they share.",
            "the-stack": f"{{tool1}} plus {{tool2}} gives you {{outcome}} in one prompt.",
            "the-warning": f"Do not {{action}} until you {{check}}.",
            "the-list": f"{{number}} things I would do differently if I started {{topic}} in {{year}}.",
            "the-receipt": f"This is the {{artifact}}. {{result}}. Here is why.",
            "the-insider": f"{{system}} tells you {{insight}}. Almost nobody {{action}}.",
            "the-impossible": f"You can {{impossible_claim}}. Here is the proof.",
            "the-comparison": f"I {{action}} the same {{topic}} {{number}} ways. One {{won}} and the others did not.",
            "the-origin": f"Every {{output}} on this channel starts in the same {{file}}. Here it is.",
            "the-deadline": f"The old {{format}} stops mattering {{timeframe}}. Here is what replaces it.",
            "the-direct-address": f"If you {{viewer_condition}}, this is the only {{topic}} you need {{timeframe}}.",
        }

        template = templates.get(formula["id"], formula["example"])

        # Fill template based on topic
        if "koda" in topic.lower() or "kodak" in topic.lower():
            fills = {
                "stat": "97",
                "topic": "companies that dominate a market",
                "consequence": "fail to survive disruption",
                "percentile": "3",
                "entity": "camera company",
                "from_state": "145,000 employees and 70% margins",
                "to_state": "bankruptcy in 17 years",
                "timeframe": "two decades",
                "mistake_area": "first 30 seconds",
                "negative_outcome": "nobody finishes your videos",
                "not_this": "topic",
                "accepted_advice": "film margins protect you",
                "contrarian_action": "built the first digital camera",
                "result": "they buried it",
                "artifact": "prototype",
                "outcome": "changed photography forever",
                "superlative": "fastest",
                "achieve_outcome": "explain corporate inertia",
                "timeframe": "six minutes",
                "deliverable": "understand why giants fall",
                "experiment": "let an AI run a documentary channel",
                "duration": "30 days",
                "benefit": "so you don't have to",
                "question": "Why did Kodak invent the digital camera and still go bankrupt?",
                "before": "Kodak Park at peak",
                "after": "abandoned factory",
                "subject": "company",
                "multiple": "four",
                "result": "click-through",
                "number": "nine",
                "category": "viewed",
                "tool1": "archival footage",
                "tool2": "AI narration",
                "outcome": "cinematic documentary",
                "action": "upload another video",
                "check": "your hook score",
                "year": "2026",
                "system": "YouTube",
                "insight": "which videos are underperforming",
                "action": "opens the report",
                "impossible_claim": "write, title, thumbnail and schedule a week of videos without opening an editor",
                "won": "held 62% retention",
                "output": "video",
                "file": "12-line script",
                "format": "description format",
                "viewer_condition": "have under a thousand subscribers",
            }
        else:
            fills = {
                "stat": "90",
                "topic": topic.lower(),
                "consequence": "fail to reach their potential",
                "percentile": "10",
                "entity": "creator",
                "from_state": "zero views",
                "to_state": "100k subscribers",
                "timeframe": "six months",
                "mistake_area": "opening hook",
                "negative_outcome": "viewers leave at 30 seconds",
                "not_this": "topic quality",
                "accepted_advice": "post daily to grow",
                "contrarian_action": "posted weekly with strong hooks",
                "result": "tripled retention",
                "artifact": "script template",
                "outcome": "writes viral videos",
                "superlative": "most reliable",
                "achieve_outcome": f"master {topic}",
                "deliverable": f"a {topic} script that retains",
                "experiment": "tested 21 hook formulas",
                "duration": "90 days",
                "benefit": "so you can skip the failures",
                "question": f"Why do most {topic} videos lose viewers in the first minute?",
                "before": "weak opening",
                "after": "strong hook",
                "subject": "video",
                "multiple": "5",
                "result": "retention",
                "number": "7",
                "category": "successful",
                "tool1": "trend research",
                "tool2": "hook scoring",
                "outcome": "viral script",
                "action": "publish",
                "check": "your retention graph",
                "year": "2026",
                "system": "the algorithm",
                "insight": "what keeps people watching",
                "action": "checks",
                "impossible_claim": f"write a {topic} script that holds 60% retention in one sitting",
                "won": "held 65%",
                "output": "video",
                "file": "hook + structure",
                "format": "old packaging",
                "viewer_condition": f"make {topic} content",
            }

        try:
            return template.format(**fills)
        except KeyError:
            return formula["example"]

    def _get_fix(self, property_name: str) -> str:
        """Get fix suggestion for weakest property."""
        fixes = {
            "SPECIFICITY": "swap one adjective for a number, a name or a date",
            "ADDRESS": "say 'you' in the first six words",
            "STAKES": "name what it costs them to keep doing it the current way",
            "CURIOSITY": "cut the half of the sentence that answers itself",
            "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
        }
        return fixes.get(property_name, "review the hook structure")

    def _get_formula_rationale(self, winner: HookOption, direction: CreativeDirection) -> str:
        """Explain why the winning formula fits this idea."""
        rationales = {
            "the-statistic": f"The Statistic works for {direction.title} because the Kodak story has shocking numbers (97% failure rate, 70% margins, 0.01MP) that instantly establish stakes.",
            "the-reveal": f"The Reveal fits because we have a specific artifact — the 1975 prototype — that proves the story.",
            "the-question": f"The Question matches what viewers actually search: 'Why did Kodak fail?' — it's their question, not ours.",
            "contrarian-flip": f"Contrarian Flip works because 'Kodak failed because they missed digital' is the accepted narrative; the truth (they invented it) flips it.",
            "the-mistake": f"The Mistake targets the universal creator fear: 'my opening loses viewers' — directly addressable.",
            "someone-elses-result": "Someone Else's Result would need a named comparable case, which we don't have for this specific story.",
            "the-before-after": "Before/After is perfect for Kodak — visual contrast between peak and bankruptcy is the story.",
            "the-teardown": "The Teardown would work if we were analyzing multiple corporate failures, not one deep dive.",
            "the-clock": "The Clock adds urgency but this story deserves breathing room, not a countdown.",
            "i-tried-it": "I Tried It doesn't fit — this isn't a first-person experiment.",
            "the-list": "The List could work ('7 decisions that killed Kodak') but reduces a narrative to bullet points.",
            "the-receipt": "The Receipt needs a screenshot/analytics page — we have historical documents instead.",
            "the-insider": "The Insider implies platform secrets — this is public history.",
            "the-impossible": "The Impossible Claim risks clickbait without immediate proof on screen.",
            "the-comparison": "The Comparison needs a named loser — 'Kodak vs Fujifilm' could work but narrows the story.",
            "the-origin": "The Origin works once per channel — 'every video starts with this research method.'",
            "the-deadline": "The Deadline needs a real date — 'film dies this month' would be false.",
            "the-direct-address": "Direct Address narrows too much — 'if you run a company' excludes most viewers.",
        }
        return rationales.get(winner.formula_id, f"{winner.formula_name} scored highest on specificity, address, stakes, curiosity, and brevity.")

    def save(self, result: HookScriptResult, project_dir: Path) -> Path:
        """Save hook+script result to project artifacts."""
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / "hook_script.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        return path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Hook & Script Agent")
    parser.add_argument("--direction", required=True, help="Path to creative_direction.json")
    parser.add_argument("--language", default="en")
    parser.add_argument("--hooks", type=int, default=5)
    args = parser.parse_args()

    with open(args.direction, encoding="utf-8") as f:
        direction_data = json.load(f)

    from lib.creative_director import CreativeDirection, SceneConcept
    direction = CreativeDirection(**direction_data)

    agent = HookScriptAgent()
    result = agent.generate(direction, args.language, args.hooks)
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())