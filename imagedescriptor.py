import os
import json
import time
import requests
import tempfile
from pathlib import Path
import google.generativeai as genai

# === CONFIGURATION ===
DISCOURSE_FOLDER = Path("discourse_topics")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
MODEL_NAME = "gemini-1.5-flash-latest"  # Updated model name
DELAY_BETWEEN_CALLS = 1

# Configure client
genai.configure(api_key=GOOGLE_API_KEY)
client = genai.GenerativeModel(model_name=MODEL_NAME)

# === Updated image description function using file upload ===
def describe_image_from_url(url):
    try:
        print(f"📷 Describing image: {url}")
        # Download image
        response = requests.get(url)
        response.raise_for_status()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name
        
        # Upload file to Google
        uploaded_file = genai.upload_file(temp_path)
        
        # Generate description
        response = client.generate_content([
            "You are a teaching assistant summarizing an image shared by a student in an academic discussion forum. "
            "Clearly describe the visual content of the image so that it can be semantically matched with similar forum posts later. "
            "Focus on key details like interface elements, questions visible, scoreboards, diagrams, graphs, or submission portals. "
            "Avoid guessing or making up information not visible in the image. Write in one or two factual sentences.",
            uploaded_file
        ])
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        return response.text.strip()
    except Exception as e:
        print(f"❌ Error describing image {url}: {e}")
        return None

# === Main Processing Loop ===
def describe_images_in_posts():
    files = list(DISCOURSE_FOLDER.glob("*.json"))
    print(f"📂 Found {len(files)} topic files")

    for file in files:
        print(f"\n📄 Processing: {file.name}")
        with open(file, "r", encoding="utf-8") as f:
            posts = json.load(f)

        updated = False
        for post in posts:
            images = post.get("images", [])
            if images and not post.get("image_descriptions"):
                post["image_descriptions"] = []
                for img_url in images:
                    desc = describe_image_from_url(img_url)
                    if desc:
                        post["image_descriptions"].append({
                            "url": img_url,
                            "description": desc
                        })
                        time.sleep(DELAY_BETWEEN_CALLS)
                updated = True

        if updated:
            with open(file, "w", encoding="utf-8") as f:
                json.dump(posts, f, indent=2)
            print(f"✅ Updated {file.name}")
        else:
            print("⏭️ No images to describe.")

if __name__ == "__main__":
    describe_images_in_posts()