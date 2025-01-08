import os


PROJECT_DIRS = [
    "metro",
    "examples",
    "auth_demo",
    # "app",
    # "config",
    # "migrations",
    # "models",
    # "controllers",
    "workers",
    "jobs",
]  # also consider files in the root directory


def is_project_file(file_path):
    for project_dir in PROJECT_DIRS:
        if file_path.startswith(project_dir + os.path.sep) or file_path.startswith(
            project_dir
        ):
            return True
    return file_path.endswith(".py") and os.path.sep not in file_path


def write_project_structure(root_dir, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Project Structure:\n")
        for dirpath, dirnames, filenames in os.walk(root_dir):
            if "venv" in dirpath or "__pycache__" in dirpath:
                continue
            level = dirpath.replace(root_dir, "").count(os.sep)
            indent = " " * 4 * level
            if os.path.basename(dirpath) in PROJECT_DIRS or level == 0:
                f.write(f"{indent}{os.path.basename(dirpath)}/\n")
                for filename in filenames:
                    if is_project_file(
                        os.path.join(dirpath, filename)
                    ) or filename.endswith(".py"):
                        f.write(f"{indent}    {filename}\n")
        f.write("\n")


def scrape_python_files(root_dir, output_file):
    with open(output_file, "a", encoding="utf-8") as f:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.endswith(".py"):
                    file_path = os.path.join(dirpath, filename)
                    relative_path = os.path.relpath(file_path, root_dir)

                    if is_project_file(relative_path):
                        f.write(f"#### ***** {relative_path} *****\n\n")

                        try:
                            with open(file_path, "r", encoding="utf-8") as code_file:
                                code_content = code_file.read()
                                f.write(code_content)
                                f.write("\n\n")
                        except UnicodeDecodeError:
                            print(f"Skipping file: {file_path} (UnicodeDecodeError)")


if __name__ == "__main__":
    root_directory = "."  # Current directory as the root
    output_file = "code_structure.txt"

    write_project_structure(root_directory, output_file)
    scrape_python_files(root_directory, output_file)
