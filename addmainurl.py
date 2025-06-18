import os
from pathlib import Path

MARKDOWN_DIR = Path("markdown/tools-in-data-science-public")
BASE_URL = "https://tds.s-anand.net/#"

def extract_main_heading(content: str):
    for line in content.splitlines():
        if line.startswith("## "):  # Match second-level heading
            return line[3:].strip()
    return None

def insert_main_url(md_path: Path):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "**Main URL:**" in content:
        return False  # Already added

    heading = extract_main_heading(content)
    if not heading:
        return False  # No valid heading found

    slug = heading.lower().strip().replace(" ", "-")
    full_url = f"{BASE_URL}/{slug}"
    main_url_line = f"**Main URL:** [{full_url}]({full_url})\n\n"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(main_url_line + content)
    
    return True

def main():
    updated_count = 0
    for md_file in MARKDOWN_DIR.rglob("*.md"):
        if insert_main_url(md_file):
            updated_count += 1
            print(f" Updated: {md_file.name}")

    print(f"\n Done! {updated_count} files updated.")

if __name__ == "__main__":
    main()
