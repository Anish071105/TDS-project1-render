import os
import json
from pathlib import Path

DISCOURSE_JSON_FOLDER = Path("discourse_topics")
OUTPUT_FOLDER = Path("markdown/discourse")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def format_post(post):
    content = []
    content.append(f"### Author: `{post['author']}`")
    content.append(f"[Main Thread]({post['main_thread_url']})")
    content.append(f"[Post URL]({post['url']})\n")

    full_text = f"[post_number]: {post['post_number']}\n" + post["content"]

    if "image_descriptions" in post:
        for img in post["image_descriptions"]:
            full_text += f"\n{img['description']}"

    if post.get("reply_to_post_number") is not None:
        full_text += f"\n\n[reply_to_post_number]: {post['reply_to_post_number']}"

    content.append(full_text)
    content.append("\n---\n")
    return "\n".join(content)


def convert_json_to_md(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        posts = json.load(f)

    if not posts:
        return

    topic_title = posts[0].get("topic_title", "untitled-topic")
    topic_id = posts[0].get("topic_id", "unknown")

    md_lines = [f"# Topic: {topic_title}\n"]

    for post in posts:
        md_lines.append(format_post(post))

    md_text = "\n".join(md_lines)

    out_file = OUTPUT_FOLDER / f"topic-{topic_id}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"Saved: {out_file.name}")


def main():
    files = list(DISCOURSE_JSON_FOLDER.glob("*.json"))
    print(f"Found {len(files)} JSON files to process.\n")

    for file in files:
        convert_json_to_md(file)


if __name__ == "__main__":
    main()
