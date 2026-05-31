import re


class CommandParser:
    def parse_with_at(self, content):
        text = content.strip()
        text = re.sub(r"<@!?\d+>", "", text).strip()
        text = re.sub(r"@\S+\s*", "", text, count=1).strip()
        return self._strip_slash(text)

    def parse_raw(self, content):
        text = content.strip()
        return self._strip_slash(text)

    def _strip_slash(self, text):
        if not text:
            return "", []
        if text.startswith("/"):
            text = text[1:].strip()
        if not text:
            return "", []
        parts = text.split()
        return parts[0], parts[1:] if len(parts) > 1 else []
