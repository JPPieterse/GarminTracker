"""LLM-powered analysis of Garmin health data using Claude."""

import os

import anthropic

import database as db

SYSTEM_PROMPT = """You are a helpful health and fitness analyst. The user wears a Garmin
smartwatch and has synced their health data. You have access to their recent data summary below.

Analyze the data to answer questions, spot trends, give insights, and provide actionable
recommendations. Be specific - reference actual numbers and dates from the data.

When discussing health topics, remind the user you're an AI and not a medical professional
when relevant.

Keep responses concise and well-structured. Use bullet points for clarity."""


def analyze(question: str, days: int = 30) -> str:
    """Ask a free-form question about the user's health data."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: ANTHROPIC_API_KEY not set. Please add it to your .env file."

    data_summary = db.get_data_summary(days=days)
    if not data_summary.strip() or "===" not in data_summary:
        return "No data available yet. Please sync your Garmin data first."

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Here is my recent health data:\n\n{data_summary}\n\nMy question: {question}",
            }
        ],
    )
    return message.content[0].text
