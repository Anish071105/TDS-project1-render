import os
import re
import json
import numpy as np
import openai
from pathlib import Path

# === CONFIGURATION ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError("Please set the OPENAI_API_KEY environment variable")

client = openai.OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
)

EMBEDDING_MODEL_NAME = "text-embedding-3-small"
MARKDOWN_DIR = "markdown"
DISCOURSE_DIR = os.path.join(MARKDOWN_DIR, "discourse")
TDS_DIR = os.path.join(MARKDOWN_DIR, "tools-in-data-science-public")
OUTPUT_FILE = "embedding.npz"
MAX_CHUNK_LENGTH = 1500

# === UTILITIES ===

def extract_main_url(text: str) -> str:
    patterns = [
        r"\*\*Main URL:\*\*\[.*?\]\((https?://[^\)]+)\)",
        r"\*\*Main URL:\*\*\s*\[.*?\]\((https?://[^\)]+)\)",
        r"Main URL:\s*\[.*?\]\((https?://[^\)]+)\)",
        r"\*\*Main URL:\*\*\s*(https?://[^\s\)]+)",
        r"Main URL:\s*(https?://[^\s\)]+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def chunk_text(text: str, max_length: int = MAX_CHUNK_LENGTH) -> list:
    chunks = []
    buf = []
    length = 0
    for line in text.splitlines():
        tokens = len(line)
        if buf and (line.startswith("##") or length + tokens > max_length):
            chunks.append("\n".join(buf).strip())
            buf = []
            length = 0
        buf.append(line)
        length += tokens
    if buf:
        chunks.append("\n".join(buf).strip())
    return chunks

def pack_segments(segments: list, max_length: int = MAX_CHUNK_LENGTH) -> list:
    chunks = []
    buf = ''
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if not buf:
            buf = seg
        elif len(buf) + len(seg) + 2 <= max_length:
            buf = buf + '\n\n' + seg
        else:
            chunks.append(buf)
            buf = seg
    if buf:
        if chunks and len(chunks[-1]) + len(buf) + 2 <= max_length:
            chunks[-1] += "\n\n" + buf.strip()
        else:
            chunks.append(buf.strip())
    return chunks

# === DISCOURSE MERGE LOGIC ===

def load_discourse_markdown() -> list:
    posts = []
    index = {}
    for path in Path(DISCOURSE_DIR).glob("*.md"):
        raw = path.read_text(encoding='utf-8')
        segments = raw.split('---\n')
        for seg in segments:
            author = re.search(r"### Author: `([^`]+)`", seg)
            main_thread = re.search(r"\[Main Thread\]\(([^)]+)\)", seg)
            post_url = re.search(r"\[Post URL\]\(([^)]+)\)", seg)
            post_num = re.search(r"\[post_number\]:\s*(\d+)", seg)
            reply_to = re.search(r"\[reply_to_post_number\]:\s*(\d+)", seg)
            content = re.sub(r"### Author: `[^`]+`|\[Main Thread\]\([^)]+\)|\[Post URL\]\([^)]+\)|\[post_number\]:\s*\d+|\[reply_to_post_number\]:\s*\d+", '', seg).strip()
            if not content:
                continue
            tid = main_thread.group(1).split('/')[-1] if main_thread else 'unknown'
            pn = int(post_num.group(1)) if post_num else None
            rt = int(reply_to.group(1)) if reply_to else None
            post = {
                'topic_id': tid,
                'post_number': pn,
                'reply_to': rt,
                'text': content,
                'post_url': post_url.group(1) if post_url else None,
                'main_url': main_thread.group(1) if main_thread else None
            }
            index[(tid, pn)] = post
            posts.append(post)
    units = {}
    def find_root(p):
        while p['reply_to'] and (p['topic_id'], p['reply_to']) in index:
            p = index[(p['topic_id'], p['reply_to'])]
        return p['post_number']
    for p in posts:
        root = find_root(p)
        units.setdefault((p['topic_id'], root), []).append(p)
    items = []
    for (tid, root), chain in units.items():
        chain_sorted = sorted(chain, key=lambda x: x['post_number'] or 0)
        segments = [p['text'] for p in chain_sorted]
        chunks = pack_segments(segments)
        final_post = chain_sorted[-1]
        for c in chunks:
            items.append({
                'text': c,
                'filename': f'topic-{tid}.md',
                'main_url': final_post['main_url'],
                'post_url': final_post['post_url']
            })
    return items

# === PROCESSING AND EMBEDDING ===

def process_markdown_files():
    items = []
    for fname in Path(TDS_DIR).glob("*.md"):
        md = fname.read_text(encoding='utf-8')
        main_url = extract_main_url(md)
        cleaned = re.sub(r"[*_]*Main URL[:：]*\s*\[[^\]]+\]\([^\)]+\)\s*", '', md, flags=re.IGNORECASE)
        chunks = chunk_text(cleaned)
        for c in chunks:
            items.append({'text': c, 'filename': fname.name, 'main_url': main_url})
    items.extend(load_discourse_markdown())
    return items

def embed_and_save(items: list):
    total_chunks = 0
    vectors, metadata = [], []
    for it in items:
        total_chunks += 1
        print(f"Embedding chunk {total_chunks} from {it['filename']}...")
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=it['text']
            )
            emb = response.data[0].embedding
            if emb:
                vectors.append(emb)
                meta = {'text': it['text'], 'filename': it['filename']}
                if it.get('main_url'): meta['main_url'] = it['main_url']
                if it.get('post_url'): meta['post_url'] = it['post_url']
                metadata.append(meta)
        except Exception as e:
            print(f"Embed error: {e}")
    np.savez(OUTPUT_FILE, vectors=np.array(vectors), metadata=np.array(metadata, dtype=object))
    print(f"Saved {len(vectors)} embeddings to {OUTPUT_FILE}")
    print(f"Total chunks processed: {total_chunks}")

if __name__ == '__main__':
    all_items = process_markdown_files()
    embed_and_save(all_items)
