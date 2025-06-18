# 🧑‍🏫 TDS Virtual TA — IIT Madras Data Science

A Virtual Teaching Assistant that automatically answers student queries based on **course content** and **Discourse forum discussions** for the **Tools in Data Science (TDS)** course, **Jan 2025 batch**.

🔗 **Live API**: [https://tds-project1-render.onrender.com/api/](https://tds-project1-render.onrender.com/api/)  
📁 **GitHub Repo**: [github.com/Anish071105/TDS-project1-render](https://github.com/Anish071105/TDS-project1-render)

---

## 📚 Background

As part of IIT Madras' Online Degree in Data Science, students often ask recurring questions on the Discourse forum. To assist TAs and reduce repetitive responses, this project builds an API that:

- Understands **course content** (as of **15 Apr 2025**)
- Leverages **Discourse posts** (from **1 Jan 2025 to 14 Apr 2025**)
- Uses **RAG (Retrieval-Augmented Generation)** (GPT 3.5 turbo model) to respond to queries intelligently
- Can handle optional **images** by describing them using the **Google Vision API**

---

## 🛠️ Project Pipeline

### 1. 🕸️ Scraping

- **Discourse Posts**: Scraped using `playwright`. The scraper is in [`discoursescraper.py`](./discoursescraper.py).
- **Course Content**: Retrieved from [https://tds.s-anand.net/#/2025-01](https://tds.s-anand.net/#/2025-01) and converted into Markdown using BeautifulSoup.

### 2. 🧩 Chunking

- **Discourse**: Each post was grouped along with its reply, post URL, and thread URL into a single chunk.
- **Course Content**: Cleanly chunked section-wise with metadata (like `main_url`) preserved.

### 3. 🔎 Semantic Embedding

- **Model**: OpenAI-compatible embedding model (via `AI Pipe` endpoint).
- **Storage**: Embeddings stored compactly in a single `.npz` file (`embedding.npz`) to avoid using a vector DB.
- **Tool**: Cosine similarity used to find the best matching chunks (top 2) per query.

### 4. 🧠 Image Description

- If a user uploads an image, GPT 3.5 turbo API generates a description, which is appended to the user's query for better context and retrieval.

---

## 💡 Key Learnings

1. **Image descriptions boost accuracy** by providing extra context to the model.
2. Using `.npz` files avoids the need for a separate vector database and saves space.
3. Learned how to **scrape**, **structure**, and **process** large-scale discussion data using automation tools.

---

## 🧠 Future Recommendations

- **TA Prioritization**: Responses from known TAs (like *Carlton sir* or *Jiviraj sir*) can be given higher weight during retrieval.
- Add **feedback loop** to improve responses over time using upvotes/downvotes.
- Cache common questions and their best responses to save API costs.
