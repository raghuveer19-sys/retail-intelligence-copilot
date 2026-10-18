"""Map presentation names to unchanged policy names, without rewriting evidence."""

import re


def plan_aliases(settings: dict) -> dict[str, str]:
    """Validate a small one-to-one table before processing any user question."""
    aliases = settings.get("plan_aliases", {})
    if not isinstance(aliases, dict) or len(aliases) > 20:
        raise ValueError("Plan aliases must be a small table of policy names and display names.")
    labels = list(aliases) + list(aliases.values())
    for label in labels:
        if (not isinstance(label, str) or not 1 <= len(label) <= 80
                or not re.fullmatch(r"[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*", label)):
            raise ValueError("Plan names must contain letters, numbers, single spaces or hyphens.")
    folded = [label.casefold() for label in labels]
    if len(folded) != len(set(folded)):
        raise ValueError("Each policy name and display name must be unique, ignoring case.")
    # Overlapping whole names would make a short alias inside a longer name
    # ambiguous. Reject that configuration instead of choosing one silently.
    for position, label in enumerate(labels):
        pattern = re.compile(r"(?<![\w-])" + re.escape(label) + r"(?![\w-])", re.I)
        if any(pattern.search(other) for index, other in enumerate(labels) if index != position):
            raise ValueError("Plan aliases must not overlap other configured plan names.")
    return dict(aliases)


def _replace(text: str, mapping: dict[str, str], *, hide_prefix: bool = False) -> str:
    if not isinstance(text, str):
        raise ValueError("Plan-name conversion needs text.")
    if not mapping:
        return text
    names = "|".join(re.escape(name) for name in mapping)
    prefix = r"(?:fictional[ \t]+)?" if hide_prefix else ""
    pattern = re.compile(r"(?<![\w-])" + prefix + r"(?P<name>" + names + r")(?![\w-])", re.I)
    replacements = {name.casefold(): replacement for name, replacement in mapping.items()}
    # One pass prevents a replacement from being interpreted as another alias.
    return pattern.sub(lambda match: replacements[match.group("name").casefold()], text)


def canonical_plan_names(text: str, aliases: dict[str, str]) -> str:
    """Use the existing policy labels for question resolution and retrieval."""
    return _replace(text, {display: policy for policy, display in aliases.items()})


def display_plan_names(text: str, aliases: dict[str, str]) -> str:
    """Rename final chat prose only; keep all policy conditions and limitations."""
    return _replace(text, aliases, hide_prefix=True)
