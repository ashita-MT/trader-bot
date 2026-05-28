import re


class CommandParser:
    def parse_with_at(self, content):
        text = content.strip()
        text = re.sub(r"<@!?\d+>", "", text).strip()
        text = re.sub(r"@\S+\s*", "", text, count=1).strip()
        if not text:
            return "", []
        parts = text.split()
        return parts[0], parts[1:] if len(parts) > 1 else []

    def parse_raw(self, content):
        text = content.strip()
        if not text:
            return "", []
        parts = text.split()
        return parts[0], parts[1:] if len(parts) > 1 else []
