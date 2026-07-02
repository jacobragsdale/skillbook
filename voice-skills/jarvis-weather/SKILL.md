---
name: jarvis-weather
description: "Check the weather forecast for a requested location and day. Use when Jacob asks for weather, rain chance, highs, lows, or a forecast."
---

# Weather reports

Use this skill for spoken weather forecast requests.

Before answering, get current forecast data for the requested location and day. Weather changes often, so do not rely only on memory. Use the available weather lookup tool when it provides the needed forecast; otherwise use a reliable current weather source.

Keep the response to one quick spoken report containing only:

- the requested location and day when useful for clarity
- the high temperature
- the low temperature
- the chance of rain

Do not include current conditions, wind, humidity, sunrise, alerts, explanations, links, or source details unless Jacob explicitly asks for them. If Jacob asks for alerts too, answer that as a separate brief sentence after the high, low, and rain chance.

If the location or day is missing and cannot be inferred from context, ask one short clarification question. Interpret "today", "tomorrow", and weekdays using the current date from the harness.

Example style:

"In Nashville today, the high is ninety two, the low is seventy four, and the rain chance is forty percent."

## Improving this skill

Before executing, read LEARNINGS.md in this skill's folder; entries there override the instructions above. After use, if the user corrected you or the outcome surprised you, append one dated line to LEARNINGS.md:
- YYYY-MM-DD: <what happened> -> <what to do instead>
Do not edit SKILL.md directly; lessons are folded in deliberately, not on the fly.
