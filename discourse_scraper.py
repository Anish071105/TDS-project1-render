# discourse.py
import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
CATEGORY_ID = 34
CATEGORY_JSON_URL = f"{BASE_URL}/c/courses/tds-kb/{CATEGORY_ID}.json"
AUTH_STATE_FILE = "auth.json"
DATE_FROM = datetime(2025, 1, 1)
DATE_TO = datetime(2025, 4, 14)


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")


def extract_image_urls(cooked_html):
    soup = BeautifulSoup(cooked_html, "html.parser")
    images = soup.find_all("img")
    return [img["src"] for img in images if img.get("src")]


def login_and_save_auth(playwright):
    print("🔐 No auth found. Launching browser for manual login...")
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    print("🌐 Please log in manually using Google. Then press ▶️ (Resume) in Playwright bar.")
    page.pause()
    context.storage_state(path=AUTH_STATE_FILE)
    print("✅ Login state saved.")
    browser.close()


def is_authenticated(page):
    try:
        page.goto(CATEGORY_JSON_URL, timeout=10000)
        page.wait_for_selector("pre", timeout=5000)
        json.loads(page.inner_text("pre"))
        return True
    except (TimeoutError, json.JSONDecodeError):
        return False


def fetch_all_posts_from_topic(page, topic_id, topic_slug):
    """Fetch all posts from a topic by paginating through all posts"""
    print(f"  📄 Fetching all posts for topic {topic_id}...")
    
    # First, get the topic metadata and initial posts
    topic_url = f"{BASE_URL}/t/{topic_slug}/{topic_id}.json"
    page.goto(topic_url)
    try:
        topic_data = json.loads(page.inner_text("pre"))
    except:
        topic_data = json.loads(page.content())
    
    # Get all post IDs from the topic
    post_stream = topic_data.get("post_stream", {})
    all_post_ids = post_stream.get("stream", [])
    initial_posts = post_stream.get("posts", [])
    
    # Create a dictionary to store all posts by their ID
    all_posts_dict = {}
    
    # Add initial posts to the dictionary
    for post in initial_posts:
        all_posts_dict[post["id"]] = post
    
    # If we have more post IDs than initial posts, we need to fetch the remaining ones
    if len(all_post_ids) > len(initial_posts):
        print(f"    🔄 Topic has {len(all_post_ids)} total posts, fetching remaining {len(all_post_ids) - len(initial_posts)} posts...")
        
        # Get the IDs of posts we haven't fetched yet
        fetched_post_ids = {post["id"] for post in initial_posts}
        remaining_post_ids = [pid for pid in all_post_ids if pid not in fetched_post_ids]
        
        # Fetch remaining posts in batches using the correct Discourse API endpoint
        batch_size = 20  # Discourse typically loads 20 posts at a time
        for i in range(0, len(remaining_post_ids), batch_size):
            batch_ids = remaining_post_ids[i:i + batch_size]
            
            # Use the proper Discourse API endpoint for fetching posts by IDs
            post_ids_params = '&'.join([f'post_ids[]={pid}' for pid in batch_ids])
            posts_url = f"{BASE_URL}/t/{topic_id}/posts.json?{post_ids_params}"
            
            try:
                page.goto(posts_url)
                response_text = page.inner_text("pre") if page.query_selector("pre") else page.content()
                batch_data = json.loads(response_text)
                
                # Check if we got posts in the response
                if "post_stream" in batch_data and "posts" in batch_data["post_stream"]:
                    batch_posts = batch_data["post_stream"]["posts"]
                elif "posts" in batch_data:
                    batch_posts = batch_data["posts"]
                else:
                    batch_posts = []
                
                for post in batch_posts:
                    all_posts_dict[post["id"]] = post
                    
                print(f"    ✓ Fetched batch of {len(batch_posts)} posts (IDs: {batch_ids[:3]}{'...' if len(batch_ids) > 3 else ''})")
                
                # Add a small delay to avoid rate limiting
                page.wait_for_timeout(100)
                
            except Exception as e:
                print(f"    ⚠️ Error fetching batch {batch_ids[:3]}{'...' if len(batch_ids) > 3 else ''}: {e}")
                
                # Try alternative method: fetch posts one by one if batch fails
                for post_id in batch_ids:
                    try:
                        single_post_url = f"{BASE_URL}/posts/{post_id}.json"
                        page.goto(single_post_url)
                        response_text = page.inner_text("pre") if page.query_selector("pre") else page.content()
                        post_data = json.loads(response_text)
                        
                        if "post" in post_data:
                            all_posts_dict[post_id] = post_data["post"]
                        elif "id" in post_data:
                            all_posts_dict[post_id] = post_data
                            
                        page.wait_for_timeout(50)
                        
                    except Exception as single_e:
                        print(f"    ⚠️ Failed to fetch single post {post_id}: {single_e}")
                        continue
    
    # Convert back to list, maintaining the original order based on post_stream.stream
    all_posts = []
    for post_id in all_post_ids:
        if post_id in all_posts_dict:
            all_posts.append(all_posts_dict[post_id])
        else:
            print(f"    ⚠️ Missing post ID {post_id}")
    
    print(f"    ✅ Successfully fetched {len(all_posts)} out of {len(all_post_ids)} posts for topic {topic_id}")
    return all_posts, topic_data


def scrape_posts(playwright):
    print("🔍 Starting scrape using saved session...")
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=AUTH_STATE_FILE)
    page = context.new_page()

    os.makedirs("discourse_topics", exist_ok=True)
    all_posts = []

    page_num = 0
    while True:
        paginated_url = f"{CATEGORY_JSON_URL}?page={page_num}"
        print(f"📦 Fetching page {page_num}...")
        page.goto(paginated_url)
        try:
            data = json.loads(page.inner_text("pre"))
        except:
            data = json.loads(page.content())

        topics = data.get("topic_list", {}).get("topics", [])
        if not topics:
            break

        for topic in topics:
            created_at = parse_date(topic["created_at"])
            if DATE_FROM <= created_at <= DATE_TO:
                topic_id = topic["id"]
                topic_slug = topic["slug"]
                
                # Fetch ALL posts from this topic
                posts, topic_data = fetch_all_posts_from_topic(page, topic_id, topic_slug)
                accepted_answer_id = topic_data.get("accepted_answer_post_id")

                reply_counter = {}
                for post in posts:
                    reply_to = post.get("reply_to_post_number")
                    if reply_to is not None:
                        reply_counter[reply_to] = reply_counter.get(reply_to, 0) + 1

                topic_post_list = []
                for post in posts:
                    cooked = post.get("cooked", "")
                    post_data = {
                        "topic_id": topic_id,
                        "topic_title": topic.get("title"),
                        "category_id": topic.get("category_id"),
                        "tags": topic.get("tags", []),
                        "post_id": post["id"],
                        "post_number": post["post_number"],
                        "author": post["username"],
                        "created_at": post["created_at"],
                        "updated_at": post.get("updated_at"),
                        "reply_to_post_number": post.get("reply_to_post_number"),
                        "is_reply": post.get("reply_to_post_number") is not None,
                        "reply_count": reply_counter.get(post["post_number"], 0),
                        "like_count": post.get("like_count", 0),
                        "is_accepted_answer": post["id"] == accepted_answer_id,
                        "mentioned_users": [u["username"] for u in post.get("mentioned_users", [])],
                        "url": f"{BASE_URL}/t/{topic_slug}/{topic_id}/{post['post_number']}",
                        "main_thread_url": f"{BASE_URL}/t/{topic_slug}/{topic_id}",
                        "content": BeautifulSoup(cooked, "html.parser").get_text(),
                        "images": extract_image_urls(cooked)
                    }
                    topic_post_list.append(post_data)
                    all_posts.append(post_data)

                with open(f"discourse_topics/{topic_id}.json", "w", encoding="utf-8") as tf:
                    json.dump(topic_post_list, tf, indent=2)
                    
                print(f"  💾 Saved {len(topic_post_list)} posts for topic '{topic.get('title')}'")

        page_num += 1

    with open("discourse_posts.json", "w", encoding="utf-8") as f:
        json.dump(all_posts, f, indent=2)

    print(f"✅ Scraped {len(all_posts)} posts from all topics.")
    browser.close()


def main():
    with sync_playwright() as p:
        if not os.path.exists(AUTH_STATE_FILE):
            login_and_save_auth(p)
        else:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_STATE_FILE)
            page = context.new_page()
            if not is_authenticated(page):
                print("⚠️ Session invalid. Re-authenticating...")
                browser.close()
                login_and_save_auth(p)
            else:
                print("✅ Using existing authenticated session.")
                browser.close()

        scrape_posts(p)

if __name__ == "__main__":
    main()