"""
Generates the full public site in docs/:
  docs/index.html              — Hebrew RTL product grid
  docs/products/{asin}.html   — individual product detail pages
  docs/about.html             — About page (Hebrew stub)
  docs/contact.html           — Contact page (Hebrew stub)
  docs/terms.html             — Terms of Use page (Hebrew stub)

Run: python export_page.py
Then: git add docs/ && git commit -m "Update products" && git push
"""

import json
import re
from pathlib import Path
from src.db import init_db, get_all

DOCS = Path(__file__).parent / "docs"
PRODUCTS_DIR = DOCS / "products"

GOOGLE_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800;900&display=swap" rel="stylesheet">'
)

BOOTSTRAP_RTL = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.rtl.min.css">'
)

BOOTSTRAP_JS = (
    '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>'
)

PLACEHOLDER_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' "
    "viewBox='0 0 400 300'%3E%3Crect width='400' height='300' fill='%23e5e5ea'/%3E"
    "%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' "
    "font-size='48' fill='%23aeaeb2'%3E%F0%9F%96%BC%EF%B8%8F%3C/text%3E%3C/svg%3E"
)

BASE_STYLES = """
  <style>
    * { box-sizing: border-box; }
    body {
      background: #F7F7F7;
      font-family: 'Heebo', 'Segoe UI', Arial, sans-serif;
      color: #1C1C1E;
      margin: 0;
    }

    /* ── Navbar ── */
    .site-nav {
      background: #fff;
      padding: 0 1.5rem;
      position: sticky;
      top: 0;
      z-index: 1000;
      box-shadow: 0 2px 10px rgba(0,0,0,.08);
      border-bottom: 1px solid #F0F0F0;
    }
    .site-nav .navbar-brand {
      font-size: 1.3rem;
      font-weight: 900;
      background: linear-gradient(90deg, #FF6B35, #FF9A5C);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.3px;
    }
    .site-nav .nav-link {
      color: #4A4A4A !important;
      font-weight: 600;
      font-size: .95rem;
      padding: .8rem .9rem;
      border-bottom: 3px solid transparent;
      transition: color .15s, border-color .15s;
    }
    .site-nav .nav-link:hover,
    .site-nav .nav-link.active {
      color: #FF6B35 !important;
      border-bottom-color: #FF6B35;
    }
    .navbar-toggler { border-color: #E0E0E0; }
    .navbar-toggler-icon {
      background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'%3e%3cpath stroke='rgba%280%2C0%2C0%2C.6%29' stroke-linecap='round' stroke-miterlimit='10' stroke-width='2' d='M4 7h22M4 15h22M4 23h22'/%3e%3c/svg%3e");
    }

    /* ── Hero ── */
    .hero {
      background: linear-gradient(135deg, #FF6B35 0%, #FF9A5C 50%, #FFB347 100%);
      color: #fff;
      text-align: center;
      padding: 28px 24px 24px;
    }
    .hero h1 {
      font-size: 1.6rem;
      font-weight: 900;
      margin-bottom: 4px;
      letter-spacing: -0.5px;
      text-shadow: 0 2px 8px rgba(0,0,0,.15);
    }
    .hero p { color: rgba(255,255,255,.88); font-size: .9rem; margin: 0; }

    /* ── Hero (compact) ── */
    .hero {
      background: linear-gradient(135deg, #FF6B35 0%, #FF9A5C 50%, #FFB347 100%);
      color: #fff;
      text-align: center;
      padding: 28px 24px 24px;
    }
    .hero h1 {
      font-size: 1.6rem;
      font-weight: 900;
      margin-bottom: 4px;
      letter-spacing: -0.5px;
      text-shadow: 0 2px 8px rgba(0,0,0,.15);
    }
    .hero p { color: rgba(255,255,255,.88); font-size: .9rem; margin: 0; }

    /* ── Page layout: sidebar + grid ── */
    .page-layout {
      display: flex;
      gap: 24px;
      align-items: flex-start;
      padding: 28px 0 48px;
    }

    /* ── Sidebar filters ── */
    .filter-sidebar {
      width: 220px;
      flex-shrink: 0;
      position: sticky;
      top: 70px;
    }
    .filter-sidebar h2 {
      font-size: .7rem;
      font-weight: 800;
      color: #AEAEB2;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin: 0 0 16px;
    }
    .filter-section {
      background: #fff;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,.06);
    }
    .filter-section-title {
      font-size: .72rem;
      font-weight: 800;
      color: #AEAEB2;
      text-transform: uppercase;
      letter-spacing: .8px;
      margin-bottom: 10px;
    }
    .search-wrap { position: relative; }
    .search-inner { position: relative; display: flex; align-items: center; }
    .search-box {
      width: 100%;
      border: 1.5px solid #E5E5EA;
      border-radius: 10px;
      padding: 9px 36px 9px 12px;
      font-family: 'Heebo', sans-serif;
      font-size: .9rem;
      outline: none;
      direction: rtl;
      transition: border-color .15s;
      background: #fff;
    }
    .search-box:focus { border-color: #FF6B35; }
    .search-clear {
      position: absolute;
      left: 10px;
      background: none;
      border: none;
      cursor: pointer;
      color: #AEAEB2;
      font-size: 1rem;
      line-height: 1;
      padding: 2px;
      display: none;
    }
    .search-clear:hover { color: #FF6B35; }
    .search-suggestions {
      display: none;
      position: absolute;
      top: calc(100% + 4px);
      right: 0; left: 0;
      background: #fff;
      border: 1.5px solid #E5E5EA;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(0,0,0,.12);
      z-index: 200;
      overflow: hidden;
    }
    .search-suggestions.open { display: block; }
    .suggestion-item {
      padding: 9px 13px;
      font-family: 'Heebo', sans-serif;
      font-size: .85rem;
      cursor: pointer;
      text-align: right;
      border-bottom: 1px solid #F2F2F7;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: #1C1C1E;
    }
    .suggestion-item:last-child { border-bottom: none; }
    .suggestion-item:hover, .suggestion-item.active { background: #FFF3EE; color: #FF6B35; }
    .suggestion-item mark { background: none; color: #FF6B35; font-weight: 700; }
    .filter-chips { display: flex; flex-direction: column; gap: 6px; }
    .chip {
      background: #F2F2F7;
      color: #3A3A3C;
      border: none;
      border-radius: 8px;
      padding: 7px 12px;
      font-family: 'Heebo', sans-serif;
      font-size: .85rem;
      font-weight: 600;
      cursor: pointer;
      text-align: right;
      transition: background .15s, color .15s;
    }
    .chip:hover { background: #FFE8DF; color: #FF6B35; }
    .chip.active { background: #FF6B35; color: #fff; }
    #results-count {
      font-size: .78rem;
      color: #AEAEB2;
      font-weight: 500;
      text-align: center;
      padding: 8px 0 0;
    }

    /* ── Product grid ── */
    .grid-area { flex: 1; min-width: 0; }
    .product-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
    }
    @media (max-width: 1100px) {
      .product-grid { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 767px) {
      .page-layout { flex-direction: column; }
      .filter-sidebar { width: 100%; position: static; }
      .filter-chips { flex-direction: row; flex-wrap: wrap; }
      .chip { padding: 5px 12px; }
      .product-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
    }
    @media (max-width: 479px) {
      .product-grid { grid-template-columns: 1fr; }
    }
    .no-results {
      text-align: center;
      padding: 60px 20px;
      color: #AEAEB2;
      font-size: 1rem;
      display: none;
      grid-column: 1/-1;
    }

    /* ── Product card ── */
    .product-card {
      background: #fff;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
      cursor: pointer;
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      transition: transform .2s, box-shadow .2s;
      position: relative;
    }
    .product-card:hover {
      transform: translateY(-5px);
      box-shadow: 0 10px 28px rgba(0,0,0,.13);
      color: inherit;
      text-decoration: none;
    }
    .product-card .card-img {
      width: 100%;
      height: 260px;
      object-fit: contain;
      background: #F2F2F7;
      padding: 16px;
    }
    .product-card .card-body {
      padding: 14px 16px 16px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .product-card .card-name {
      font-size: .95rem;
      font-weight: 700;
      line-height: 1.35;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .product-card .card-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: auto;
    }
    .badge-rating {
      background: #FFF3CD;
      color: #856404;
      font-size: .78rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
    }
    .card-price {
      font-size: .9rem;
      font-weight: 700;
      color: #1C1C1E;
    }
    .category-badge {
      position: absolute;
      top: 10px;
      left: 10px;
      background: #FF6B35;
      color: #fff;
      font-size: .68rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 20px;
      letter-spacing: .3px;
      text-transform: uppercase;
    }

    /* ── Product detail page ── */
    .product-detail {
      max-width: 700px;
      margin: 0 auto;
      padding: 32px 16px 64px;
    }
    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #6E6E73;
      text-decoration: none;
      font-size: .9rem;
      margin-bottom: 24px;
      transition: color .15s;
    }
    .back-link:hover { color: #FF6B35; }
    .detail-img-wrap {
      background: #F2F2F7;
      border-radius: 20px;
      padding: 24px;
      text-align: center;
      margin-bottom: 28px;
      box-shadow: 0 4px 16px rgba(0,0,0,.07);
    }
    .detail-img-wrap img {
      max-width: 100%;
      max-height: 420px;
      object-fit: contain;
      border-radius: 10px;
    }
    .detail-title {
      font-size: 1.45rem;
      font-weight: 800;
      line-height: 1.3;
      margin-bottom: 14px;
    }
    .detail-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }
    .detail-meta .price-tag {
      font-size: 1.25rem;
      font-weight: 800;
      color: #1C1C1E;
    }
    .price-note {
      display: block;
      font-size: .72rem;
      color: #999;
      font-weight: 400;
      margin-top: 2px;
    }
    .detail-meta .reviews-count {
      color: #6E6E73;
      font-size: .88rem;
    }
    .divider { border: none; border-top: 1px solid #E5E5EA; margin: 20px 0; }
    .detail-desc {
      font-size: 1rem;
      line-height: 1.85;
      color: #3A3A3C;
      margin-bottom: 32px;
    }
    .buy-btn {
      display: block;
      width: 100%;
      background: #FFD814;
      color: #0F1111;
      font-family: 'Heebo', sans-serif;
      font-size: 1.1rem;
      font-weight: 700;
      padding: 15px 32px;
      border-radius: 10px;
      border: none;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
      transition: background .15s, transform .1s;
    }
    .buy-btn:hover {
      background: #F7CA00;
      color: #0F1111;
      transform: translateY(-1px);
    }
    .buy-btn:active { transform: translateY(0); }
    .tiktok-wrap {
      margin: 28px 0;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,.1);
      background: #000;
      text-align: center;
    }
    .tiktok-wrap iframe {
      border: none;
      width: 100%;
      max-width: 380px;
      height: 680px;
      border-radius: 16px;
    }

    /* ── Static pages (about / contact / terms) ── */
    .static-page {
      max-width: 760px;
      margin: 0 auto;
      padding: 40px 16px 80px;
    }
    .static-card {
      background: #fff;
      border-radius: 20px;
      padding: 40px 36px;
      box-shadow: 0 2px 12px rgba(0,0,0,.07);
      line-height: 1.85;
    }
    .static-card h1 { font-size: 1.6rem; font-weight: 800; margin-bottom: 20px; }
    .static-card p { color: #3A3A3C; }
    .wip-badge {
      display: inline-block;
      background: #FFF3CD;
      color: #856404;
      border-radius: 8px;
      padding: 8px 16px;
      font-size: .9rem;
      font-weight: 600;
      margin-bottom: 20px;
    }

    /* ── Footer ── */
    .site-footer {
      background: #FFF8F5;
      color: #8A8A8E;
      text-align: center;
      padding: 28px 16px;
      font-size: .82rem;
      border-top: 1px solid #F0E8E4;
    }
    .site-footer a { color: #FF6B35; text-decoration: none; }
    .site-footer a:hover { text-decoration: underline; }
  </style>
"""


def nav_html(active: str = "products", depth: str = "") -> str:
    links = [
        ("products", f"{depth}index.html", "עמוד מוצרים"),
        ("about",    f"{depth}about.html",   "עלינו"),
        ("contact",  f"{depth}contact.html",  "צור קשר"),
        ("terms",    f"{depth}terms.html",    "תנאי שימוש"),
    ]
    items = ""
    for key, href, label in links:
        cls = "nav-link active" if key == active else "nav-link"
        items += f'<li class="nav-item"><a class="{cls}" href="{href}">{label}</a></li>'

    return f"""
<nav class="navbar navbar-expand-md site-nav">
  <div class="container">
    <a class="navbar-brand" href="{depth}index.html">המוצרים שלי</a>
    <button class="navbar-toggler" type="button"
            data-bs-toggle="collapse" data-bs-target="#navMenu">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navMenu">
      <ul class="navbar-nav me-auto">
        {items}
      </ul>
    </div>
  </div>
</nav>"""


def footer_html() -> str:
    return """
<footer class="site-footer">
  <p class="mb-1">המוצרים שלי · מוצרי אמזון מובחרים לשלוח לישראל 🇮🇱</p>
  <p class="mb-0"><a href="terms.html">תנאי שימוש</a> · <a href="contact.html">צור קשר</a></p>
</footer>"""


def head_html(title: str, extra_css: str = "") -> str:
    return f"""<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  {GOOGLE_FONTS}
  {BOOTSTRAP_RTL}
  {BASE_STYLES}
  {extra_css}
</head>"""


# ── Index page ─────────────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "byotools": "BYOTOOLS",
    "Best Sellers Kitchen Dining": "מטבח ואוכל",
    "Best Sellers Sports Outdoors": "ספורט וטבע",
    "Best Sellers Tools Home Improvement": "כלים ושיפוצים",
}


def build_index(products: list[dict]) -> str:
    categories = sorted({p.get("category") or "" for p in products if p.get("category")})

    cards = ""
    for p in products:
        img      = p.get("image_url") or PLACEHOLDER_SVG
        name_he  = (p.get("name_he") or p.get("name") or p["asin"]).replace('"', "&quot;")
        rating   = p.get("rating") or 0
        price    = p.get("price") or 0
        cat      = p.get("category") or ""
        asin     = p["asin"]

        rating_str = f"⭐ {rating:.1f}" if rating else "—"
        price_str  = f"${price:.2f}" if price else "—"
        cat_label  = CATEGORY_LABELS.get(cat, cat[:18])
        cat_badge  = f'<span class="category-badge">{cat_label}</span>' if cat else ""

        cards += f"""
    <a class="product-card" href="products/{asin}.html"
       data-price="{price}" data-rating="{rating}" data-category="{cat}" data-name="{name_he[:80].lower()}">
      {cat_badge}
      <img class="card-img" src="{img}" alt="{name_he[:60]}" loading="lazy"
           onerror="this.src='{PLACEHOLDER_SVG}'">
      <div class="card-body">
        <div class="card-name">{name_he[:70]}</div>
        <div class="card-meta">
          <span class="badge-rating">{rating_str}</span>
          <span class="card-price">{price_str}</span>
        </div>
      </div>
    </a>"""

    count = len(products)

    sidebar = f"""
    <aside class="filter-sidebar">
      <div class="filter-section">
        <div class="search-wrap">
          <div class="search-inner">
            <input type="text" id="search-input" class="search-box" placeholder="🔍 חיפוש מוצר..." oninput="onSearchInput()" autocomplete="off" onkeydown="onSearchKey(event)">
            <button class="search-clear" id="search-clear" onclick="clearSearch()" tabindex="-1">✕</button>
          </div>
          <div class="search-suggestions" id="search-suggestions"></div>
        </div>
      </div>
      <div class="filter-section">
        <div class="filter-section-title">מחיר</div>
        <div class="filter-chips" id="price-chips">
          <button class="chip active" data-max="99999" onclick="setPrice(this)">הכל</button>
          <button class="chip" data-max="10"    onclick="setPrice(this)">עד $10</button>
          <button class="chip" data-max="20"    onclick="setPrice(this)">עד $20</button>
          <button class="chip" data-max="50"    onclick="setPrice(this)">עד $50</button>
          <button class="chip" data-max="75"    onclick="setPrice(this)">עד $75</button>
          <button class="chip" data-max="150"   onclick="setPrice(this)">עד $150</button>
        </div>
      </div>

      <div class="filter-section">
        <div class="filter-section-title">דירוג</div>
        <div class="filter-chips" id="rating-chips">
          <button class="chip active" data-min="0"   onclick="setRating(this)">הכל</button>
          <button class="chip" data-min="4"   onclick="setRating(this)">⭐ 4 ומעלה</button>
          <button class="chip" data-min="4.5" onclick="setRating(this)">⭐ 4.5 ומעלה</button>
        </div>
      </div>

      <div class="filter-section">
        <div class="filter-section-title">קטגוריה</div>
        <div class="filter-chips" id="cat-chips">
          <button class="chip active" data-cat="" onclick="setCat(this)">הכל</button>
          {"".join(f'<button class="chip" data-cat="{c}" onclick="setCat(this)">{CATEGORY_LABELS.get(c, c)}</button>' for c in categories)}
        </div>
      </div>

      <div id="results-count"></div>
    </aside>"""

    filter_js = """
<script>
  let activePrice  = 99999;
  let activeRating = 0;
  let activeCat    = "";

  let activeSuggestion = -1;

  function applyFilters() {
    const query = (document.getElementById("search-input").value || "").toLowerCase().trim();
    // show/hide clear button
    document.getElementById("search-clear").style.display = query ? "block" : "none";
    const cards = document.querySelectorAll(".product-card");
    let visible = 0;
    cards.forEach(c => {
      const price  = parseFloat(c.dataset.price)  || 0;
      const rating = parseFloat(c.dataset.rating) || 0;
      const cat    = c.dataset.category || "";
      const name   = c.dataset.name || "";
      const show   = price <= activePrice
                  && rating >= activeRating
                  && (activeCat === "" || cat === activeCat)
                  && (query === "" || name.includes(query));
      c.style.display = show ? "" : "none";
      if (show) visible++;
    });
    const total = cards.length;
    document.getElementById("results-count").textContent =
      visible === total ? `${total} מוצרים` : `${visible} מתוך ${total}`;
  }

  function closeSuggestions() {
    document.getElementById("search-suggestions").classList.remove("open");
    activeSuggestion = -1;
  }

  function onSearchInput() {
    applyFilters();
    const q = (document.getElementById("search-input").value || "").toLowerCase().trim();
    const box = document.getElementById("search-suggestions");
    if (q.length < 2) { closeSuggestions(); return; }
    const cards = document.querySelectorAll(".product-card");
    const seen = new Set();
    const matches = [];
    cards.forEach(c => {
      const name = c.dataset.name || "";
      if (name.includes(q) && !seen.has(name)) { seen.add(name); matches.push(name); }
    });
    if (matches.length === 0) { closeSuggestions(); return; }
    activeSuggestion = -1;
    box.innerHTML = matches.slice(0, 6).map((m, i) => {
      const hi = m.replace(new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'g'), `<mark>$&</mark>`);
      return `<div class="suggestion-item" onmousedown="pickSuggestion(this)" data-val="${m}">${hi}</div>`;
    }).join("");
    box.classList.add("open");
  }

  function pickSuggestion(el) {
    document.getElementById("search-input").value = el.dataset.val;
    closeSuggestions();
    applyFilters();
  }

  function clearSearch() {
    document.getElementById("search-input").value = "";
    closeSuggestions();
    applyFilters();
    document.getElementById("search-input").focus();
  }

  function onSearchKey(e) {
    const box = document.getElementById("search-suggestions");
    const items = box.querySelectorAll(".suggestion-item");
    if (e.key === "Escape") { closeSuggestions(); return; }
    if (e.key === "Enter") {
      // if a suggestion is highlighted, pick it; otherwise just close dropdown and keep text
      if (box.classList.contains("open") && activeSuggestion >= 0) {
        e.preventDefault();
        pickSuggestion(items[activeSuggestion]);
      } else {
        closeSuggestions();
      }
      return;
    }
    if (!box.classList.contains("open") || items.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeSuggestion = Math.min(activeSuggestion + 1, items.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeSuggestion = Math.max(activeSuggestion - 1, -1);
    } else { return; }
    items.forEach((el, i) => el.classList.toggle("active", i === activeSuggestion));
  }

  document.addEventListener("click", e => {
    if (!e.target.closest(".search-wrap")) closeSuggestions();
  });

  function setPrice(btn) {
    document.querySelectorAll("#price-chips .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activePrice = parseFloat(btn.dataset.max);
    applyFilters();
  }
  function setRating(btn) {
    document.querySelectorAll("#rating-chips .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeRating = parseFloat(btn.dataset.min);
    applyFilters();
  }
  function setCat(btn) {
    document.querySelectorAll("#cat-chips .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeCat = btn.dataset.cat;
    applyFilters();
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyFilters();

    // Restore scroll position when returning from a product page
    const savedScroll = sessionStorage.getItem("productGridScroll");
    if (savedScroll !== null) {
      sessionStorage.removeItem("productGridScroll");
      requestAnimationFrame(() => {
        window.scrollTo({ top: parseInt(savedScroll, 10), behavior: "instant" });
      });
    }

    // Save scroll position before navigating to a product page
    document.querySelectorAll(".product-card").forEach(card => {
      card.addEventListener("click", () => {
        sessionStorage.setItem("productGridScroll", window.scrollY);
      });
    });
  });
</script>"""

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("המוצרים שלי — מוצרים מנצחים")}
<body>
{nav_html("products")}

<div class="hero">
  <h1>המוצרים שלי 🇮🇱</h1>
  <p>{count} מוצרים מאמאזון · משלוח לישראל</p>
</div>

<div class="container">
  <div class="page-layout">
    {sidebar}
    <div class="grid-area">
      <div class="product-grid" id="grid">
        {cards}
      </div>
      <p class="no-results" id="no-results">לא נמצאו מוצרים עם הפילטרים שנבחרו</p>
    </div>
  </div>
</div>

{footer_html()}
{BOOTSTRAP_JS}
{filter_js}
</body>
</html>"""


# ── Product detail page ────────────────────────────────────────────────────

def build_product_page(p: dict) -> str:
    asin         = p["asin"]
    name         = (p.get("name_he") or p.get("name") or asin).replace('"', "&quot;")
    img          = p.get("image_url") or PLACEHOLDER_SVG
    rating_str   = f"⭐ {p['rating']:.1f}" if p.get("rating") else ""
    reviews_str  = f"({p['reviews']:,} ביקורות)" if p.get("reviews") else ""
    price_str    = f"${p['price']:.2f}" if p.get("price") else ""
    updated_raw  = p.get("updated_at") or ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
        updated_label = dt.strftime("%-d/%-m/%Y")
    except Exception:
        updated_label = ""
    price_note   = f'<span class="price-note">נבדק {updated_label} · המחיר עשוי להשתנות</span>' if updated_label else ""
    affiliate    = p.get("link") or f"https://www.amazon.com/dp/{asin}/?tag=eskl20-20"
    desc_he      = p.get("description_he") or "תיאור המוצר יתעדכן בקרוב."
    tiktok_url   = p.get("tiktok_url") or ""
    tiktok_video_id = ""
    if tiktok_url:
        m = re.search(r"/video/(\d+)", tiktok_url)
        if m:
            tiktok_video_id = m.group(1)

    rating_block = ""
    if rating_str or price_str:
        rating_block = f"""
    <div class="detail-meta">
      {f'<span class="badge-rating">{rating_str}</span>' if rating_str else ""}
      {f'<span class="reviews-count">{reviews_str}</span>' if reviews_str else ""}
      {f'<span class="price-tag">{price_str}{price_note}</span>' if price_str else ""}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html(f"{name[:50]} — המוצרים שלי")}
<body>
{nav_html("products", depth="../")}

<div class="product-detail">
  <a class="back-link" href="../index.html">&#8592; חזרה למוצרים</a>

  <div class="detail-img-wrap">
    <img src="{img}" alt="{name[:60]}"
         onerror="this.src='{PLACEHOLDER_SVG}'">
  </div>

  <h1 class="detail-title">{name}</h1>
  {rating_block}
  <hr class="divider">

  <p class="detail-desc">{desc_he}</p>

  <a class="buy-btn" href="{affiliate}" target="_blank" rel="noopener noreferrer">
    🛒&nbsp; רכישה באמזון
  </a>

  {f'''<div class="tiktok-wrap">
    <iframe src="https://www.tiktok.com/embed/v2/{tiktok_video_id}"
            allowfullscreen allow="autoplay; encrypted-media">
    </iframe>
  </div>''' if tiktok_video_id else ""}
</div>

{footer_html()}
{BOOTSTRAP_JS}
</body>
</html>"""


# ── Static pages ───────────────────────────────────────────────────────────

def build_about() -> str:
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("עלינו — המוצרים שלי")}
<body>
{nav_html("about")}
<div class="static-page">
  <div class="static-card">
    <h1>עלינו</h1>
    <div class="wip-badge">⏳ עמוד בבנייה — תוכן יתווסף בקרוב</div>
    <p>
      ברוכים הבאים ל<strong>המוצרים שלי</strong> — המקום שבו תמצאו את מיטב
      המוצרים מאמזון שמגיעים ישירות לישראל.
    </p>
    <p>
      אנחנו בוחרים בקפידה מוצרים בעלי דירוג גבוה, מחיר הוגן ומשלוח מאומת לישראל.
      כל קניה דרך הקישורים שלנו עוזרת לנו להמשיך לפעול — תודה על התמיכה!
    </p>
  </div>
</div>
{footer_html()}
{BOOTSTRAP_JS}
</body>
</html>"""


def build_contact() -> str:
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("צור קשר — המוצרים שלי")}
<body>
{nav_html("contact")}
<div class="static-page">
  <div class="static-card">
    <h1>צור קשר</h1>
    <p style="color:#6E6E73; margin-bottom:28px;">נשמח לשמוע ממכם — שאלות, הצעות, או מוצרים שתרצו שנוסיף לאתר.</p>

    <div style="background:#FFF3EE; border-radius:14px; padding:24px 20px; margin-bottom:24px; text-align:center;">
      <div style="font-size:2rem; margin-bottom:10px;">✉️</div>
      <div style="font-weight:700; font-size:1rem; margin-bottom:6px;">דוא"ל</div>
      <a href="mailto:toppickp@gmail.com" style="color:#FF6B35; font-size:1.05rem; font-weight:600; text-decoration:none;">toppickp@gmail.com</a>
    </div>

    <p style="font-size:.88rem; color:#AEAEB2; text-align:center;">אנו מגיבים תוך 1–2 ימי עסקים.</p>
  </div>
</div>
{footer_html()}
{BOOTSTRAP_JS}
</body>
</html>"""


def build_terms() -> str:
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("תנאי שימוש — המוצרים שלי")}
<body>
{nav_html("terms")}
<div class="static-page">
  <div class="static-card">
    <h1>תנאי שימוש</h1>
    <p style="color:#6E6E73; font-size:.9rem; margin-bottom:28px;">עדכון אחרון: מאי 2026</p>

    <h2 style="font-size:1.05rem; font-weight:800; margin:24px 0 8px;">1. גילוי נאות — קישורי שותפים</h2>
    <p>האתר משתתף בתכנית השותפים של אמזון (Amazon Associates). חלק מהקישורים באתר הם קישורי שותפים — אם תבצעו רכישה דרכם, אנו עשויים לקבל עמלה ללא כל עלות נוספת עבורכם.</p>

    <h2 style="font-size:1.05rem; font-weight:800; margin:24px 0 8px;">2. דיוק מידע</h2>
    <p>המחירים, הזמינות ופרטי המוצרים מתעדכנים באופן שוטף ישירות מאמזון. למרות שאנו עושים כמיטב יכולתנו לשמור על עדכניות המידע, ייתכנו שינויים בין המחיר המוצג לבין המחיר בפועל בזמן הרכישה. אנו ממליצים לאמת את הפרטים בעמוד המוצר באמזון לפני ביצוע הרכישה.</p>

    <h2 style="font-size:1.05rem; font-weight:800; margin:24px 0 8px;">3. הגבלת אחריות</h2>
    <p>האתר אינו אחראי לאיכות המוצרים, זמני האספקה, מדיניות ההחזרות, או כל נושא הקשור לשירות הלקוחות של אמזון או הספקים. כל רכישה היא עסקה ישירה בינכם לבין אמזון, בכפוף לתנאי השימוש שלהם.</p>

    <h2 style="font-size:1.05rem; font-weight:800; margin:24px 0 8px;">4. קישורים חיצוניים</h2>
    <p>לחיצה על כפתורי הרכישה תעביר אתכם לאתר אמזון. אנו אינם אחראים לתוכן, מדיניות הפרטיות, או פעולותיו של אתר אמזון. השימוש באמזון כפוף לתנאי השימוש שלהם.</p>

    <h2 style="font-size:1.05rem; font-weight:800; margin:24px 0 8px;">5. שינויים בתנאים</h2>
    <p>אנו שומרים לעצמנו את הזכות לשנות תנאים אלה בכל עת. המשך השימוש באתר לאחר פרסום שינויים מהווה הסכמה לתנאים המעודכנים.</p>

    <h2 style="font-size:1.05rem; font-weight:800; margin:24px 0 8px;">6. יצירת קשר</h2>
    <p>לשאלות בנושא תנאי השימוש: <a href="mailto:toppickp@gmail.com" style="color:#FF6B35;">toppickp@gmail.com</a></p>
  </div>
</div>
{footer_html()}
{BOOTSTRAP_JS}
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────

def build():
    init_db()
    raw = [p for p in get_all() if p["status"] == "ready_for_video"]

    # Normalise field names for the template functions
    products = []
    for p in raw:
        products.append({
            "asin":           p["asin"],
            "name":           p.get("name") or p["asin"],
            "name_he":        p.get("name_he") or "",
            "category":       p.get("category") or "",
            "rating":         round(p.get("rating") or 0, 1),
            "price":          round(p.get("price_usd") or 0, 2),
            "reviews":        p.get("review_count") or 0,
            "link":           p.get("affiliate_link") or f"https://www.amazon.com/dp/{p['asin']}/?tag=eskl20-20",
            "image_url":      p.get("image_url") or "",
            "description_he": p.get("description_he") or "",
            "tiktok_url":     p.get("tiktok_url") or "",
            "updated_at":     p.get("updated_at") or "",
        })

    DOCS.mkdir(exist_ok=True)
    PRODUCTS_DIR.mkdir(exist_ok=True)

    # Index
    (DOCS / "index.html").write_text(build_index(products), encoding="utf-8")
    print(f"✓ docs/index.html  ({len(products)} products)")

    # Per-product pages
    for p in products:
        path = PRODUCTS_DIR / f"{p['asin']}.html"
        path.write_text(build_product_page(p), encoding="utf-8")
    print(f"✓ docs/products/   ({len(products)} pages)")

    # Static pages
    (DOCS / "about.html").write_text(build_about(),   encoding="utf-8")
    (DOCS / "contact.html").write_text(build_contact(), encoding="utf-8")
    (DOCS / "terms.html").write_text(build_terms(),   encoding="utf-8")
    print("✓ docs/about.html  docs/contact.html  docs/terms.html")

    print("\nDone! Push with:")
    print("  git add docs/ && git commit -m 'Update products' && git push")


if __name__ == "__main__":
    build()
