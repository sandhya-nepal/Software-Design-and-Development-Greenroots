"""Consistent, collision-free identifier generation for every record type."""


class IdGenerator:
    """Produces IDs such as SITE-001 that are unique within a given collection."""

    def __init__(self):
        self._counters = {}

    def peek(self, prefix, existing, width=3):
        """Return the next free ID without reserving it."""
        number = self._counters.get(prefix, 0)
        while True:
            number += 1
            candidate = f"{prefix}-{number:0{width}d}"
            if candidate not in existing:
                return candidate, number

    def next_id(self, prefix, existing, width=3):
        candidate, number = self.peek(prefix, existing, width)
        self._counters[prefix] = number
        return candidate

    def suggest(self, prefix, existing, width=3):
        return self.peek(prefix, existing, width)[0]
