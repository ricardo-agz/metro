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