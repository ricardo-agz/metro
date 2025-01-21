import black
import isort
import click


def insert_line_without_duplicating(file_path, line):
    normalized_line = line.strip() + "\n"

    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    # Strip existing lines of trailing whitespace for accurate comparison
    stripped_lines = [l.strip() for l in lines]

    if line.strip() not in stripped_lines:
        lines.append(normalized_line)

    # Ensure all lines end with a newline character
    lines = [l if l.endswith("\n") else l + "\n" for l in lines]

    with open(file_path, "w") as f:
        f.writelines(lines)


def format_python(source_code: str) -> str:
    try:
        # First, sort the imports using isort
        sorted_code = isort.code(source_code)
        # Then apply Black formatting
        return black.format_str(sorted_code, mode=black.FileMode())
    except Exception as e:
        click.echo(click.style(f"Error formatting code: {e}", fg="red"))
        return source_code
