"""Knowledge base retrieval — loads domain knowledge modules and matches them to questions."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

logger = structlog.get_logger()

# Directory containing knowledge markdown files
_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"

# Keyword index — maps keywords to module filenames
# Each module has a set of trigger keywords. When a user's question contains
# any of these keywords, that module gets included in the coach's context.
_MODULE_KEYWORDS: dict[str, list[str]] = {
    "strength-programming": [
        "strength", "progressive overload", "periodization", "deload",
        "compound", "isolation", "barbell", "dumbbell", "bench press",
        "squat", "deadlift", "overhead press", "sets and reps", "rep range",
        "powerlifting", "program", "split", "training plan", "workout plan",
        "rest between sets", "frequency",
    ],
    "hypertrophy-science": [
        "hypertrophy", "muscle growth", "muscle gain", "building muscle",
        "volume", "time under tension", "tempo", "mind-muscle",
        "muscle protein synthesis", "bulking", "muscle size",
        "bodybuilding", "aesthetic", "definition", "physique",
    ],
    "body-composition": [
        "body composition", "body fat", "lean mass", "muscle mass",
        "recomp", "recomposition", "body fat percentage", "bmi",
        "skinny fat", "cutting", "bulk", "maintain muscle",
        "measurements", "dexa", "body scan",
    ],
    "nutrition-fundamentals": [
        "nutrition", "diet", "protein", "carbs", "carbohydrates", "fats",
        "macros", "calories", "meal", "eating", "food", "supplement",
        "creatine", "vitamin", "hydration", "water", "pre-workout meal",
        "post-workout meal", "breakfast", "dinner", "lunch",
    ],
    "weight-loss": [
        "weight loss", "lose weight", "fat loss", "lose fat", "deficit",
        "calorie deficit", "cutting weight", "diet", "tdee",
        "maintenance calories", "plateau", "refeed", "diet break",
        "metabolism", "metabolic", "appetite", "hunger",
    ],
    "sleep-recovery": [
        "sleep", "recovery", "rest", "overtraining", "tired", "fatigue",
        "hrv", "heart rate variability", "deep sleep", "rem",
        "nap", "insomnia", "sleep quality", "sleep score",
        "growth hormone", "testosterone", "cortisol",
    ],
    "running-programming": [
        "running", "run", "jog", "marathon", "half marathon", "5k", "10k",
        "pace", "tempo", "intervals", "easy run", "long run",
        "cadence", "taper", "race", "parkrun", "trail",
        "aerobic base", "80/20",
    ],
    "heart-rate-training": [
        "heart rate", "hr zone", "zone 2", "zone 3", "zone 4", "zone 5",
        "max heart rate", "resting heart rate", "cardiac drift",
        "heart rate recovery", "aerobic", "anaerobic", "threshold",
        "bpm", "heart rate training",
    ],
    "wearable-data-interpretation": [
        "garmin", "body battery", "stress score", "vo2 max", "vo2max",
        "training load", "training status", "intensity minutes",
        "wearable", "watch", "tracker", "spo2", "blood oxygen",
        "fitness age", "steps", "daily steps",
    ],
    "injury-prevention": [
        "injury", "pain", "hurt", "sore", "soreness", "ache",
        "shin splints", "knee", "shoulder", "back pain", "lower back",
        "it band", "plantar fasciitis", "tendon", "mobility",
        "stretching", "warm up", "cool down", "foam roll",
        "recovery", "rehab",
    ],
    "sauna-heat-therapy": [
        "sauna", "steam room", "heat", "cold plunge", "ice bath",
        "cold shower", "heat therapy", "infrared", "heat shock",
        "hot tub", "contrast therapy",
    ],
    "meditation-mindfulness": [
        "meditation", "meditate", "mindfulness", "breathing",
        "breathwork", "box breathing", "calm", "focus", "mental",
        "visualization", "body scan", "yoga", "mindful",
        "present", "awareness",
    ],
    "mental-resilience-motivation": [
        "motivation", "discipline", "consistency", "habit",
        "burnout", "plateau", "stuck", "give up", "skip",
        "lazy", "routine", "willpower", "mental", "mindset",
        "goal setting", "accountability", "procrastination",
        "perfectionism", "all or nothing",
    ],
    "stress-wellbeing": [
        "stress", "stressed", "anxiety", "anxious", "overwhelmed",
        "work-life", "balance", "burnout", "cortisol",
        "relax", "rest day", "mental health", "wellbeing",
        "parasympathetic", "nervous system",
    ],
    "garmin-api-data": [
        "garmin", "api", "body battery", "stress score", "training load",
        "training status", "vo2", "sync", "data", "metrics",
        "wearable", "watch data", "garmin connect",
    ],
}

# Cache loaded modules in memory
_module_cache: dict[str, str] = {}


def _load_module(name: str) -> str | None:
    """Load a knowledge module from disk, with caching."""
    if name in _module_cache:
        return _module_cache[name]

    path = _KNOWLEDGE_DIR / f"{name}.md"
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    _module_cache[name] = content
    return content


def clear_cache() -> None:
    """Clear the module cache (useful after adding new modules)."""
    _module_cache.clear()


def get_relevant_knowledge(question: str, max_modules: int = 3) -> str:
    """Match a user's question against the knowledge base and return relevant content.

    Returns a formatted string ready to inject into a system prompt.
    Uses keyword matching — counts how many keywords from each module
    appear in the question, returns the top matches.
    """
    question_lower = question.lower()

    # Score each module by keyword hits
    scores: list[tuple[str, int]] = []
    for module_name, keywords in _MODULE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in question_lower)
        if score > 0:
            scores.append((module_name, score))

    # Sort by score descending, take top N
    scores.sort(key=lambda x: x[1], reverse=True)
    top_modules = scores[:max_modules]

    if not top_modules:
        return ""

    # Load and concatenate
    parts: list[str] = []
    for module_name, _score in top_modules:
        content = _load_module(module_name)
        if content:
            # Trim to first 1500 chars to keep token usage reasonable
            trimmed = content[:1500]
            if len(content) > 1500:
                # Cut at last complete sentence
                last_period = trimmed.rfind(".")
                if last_period > 500:
                    trimmed = trimmed[: last_period + 1]
            parts.append(trimmed)

    if not parts:
        return ""

    return "\n\n## Relevant Domain Knowledge\n\n" + "\n\n---\n\n".join(parts)


def list_available_modules() -> list[dict[str, str]]:
    """List all knowledge modules and their status."""
    modules = []
    for name in sorted(_MODULE_KEYWORDS.keys()):
        path = _KNOWLEDGE_DIR / f"{name}.md"
        modules.append({
            "name": name,
            "available": path.exists(),
            "keywords": len(_MODULE_KEYWORDS[name]),
        })
    return modules
