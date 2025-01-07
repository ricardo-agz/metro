import re
import inflect


p = inflect.engine()


def is_valid_identifier(name: str) -> bool:
    """Check if the provided name is a valid Python identifier."""
    import re

    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) is not None


def split_on_case_change(string):
    """Split a string on case changes."""
    return re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", string)


def to_snake_case(string):
    """Convert a string to snake_case."""
    words = split_on_case_change(string)
    return "_".join(word.lower() for word in words)


def to_kebab_case(string):
    """Convert a string to kebab-case."""
    words = split_on_case_change(string)
    return "-".join(word.lower() for word in words)


def to_camel_case(string):
    """Convert a string to camelCase."""
    words = split_on_case_change(string)
    return words[0].lower() + "".join(word.capitalize() for word in words[1:])


def to_pascal_case(string):
    """Convert a string to PascalCase."""
    words = split_on_case_change(string)
    return "".join(word.capitalize() for word in words)


def pluralize(word):
    """Pluralize a word, maintaining its original case."""
    words = split_on_case_change(word)
    if len(words) == 1:
        if word.isupper():
            return p.plural(word).upper()
        elif word.istitle():
            return p.plural(word).title()
        else:
            return p.plural(word)
    else:
        # For compound words, pluralize the last word
        words[-1] = p.plural(words[-1])
        return "".join(words)
