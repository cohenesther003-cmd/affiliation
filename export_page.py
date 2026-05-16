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
      padding: 0 1.25rem;
      position: sticky;
      top: 0;
      z-index: 1000;
      box-shadow: 0 2px 10px rgba(0,0,0,.08);
      border-bottom: 1px solid #F0F0F0;
      min-height: 48px;
    }
    .site-nav .navbar {
      padding-top: 6px;
      padding-bottom: 6px;
    }
    .site-nav .navbar-brand {
      font-size: 1.2rem;
      font-weight: 900;
      background: linear-gradient(90deg, #FF6B35, #FF9A5C);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.3px;
      margin: 0;
    }
    .site-nav .nav-link {
      color: #4A4A4A !important;
      font-weight: 600;
      font-size: .9rem;
      padding: .55rem .8rem;
      transition: color .15s;
    }
    .site-nav .nav-link:hover,
    .site-nav .nav-link.active {
      color: #FF6B35 !important;
    }
    .site-nav .navbar-nav {
      flex-direction: row;
      gap: 4px;
    }
    /* Mobile: hide redundant brand (hero already shows Top Picks); tabs sit side-by-side, no hamburger */
    @media (max-width: 767px) {
      .site-nav .navbar-brand { display: none; }
      .site-nav { padding: 0 .75rem; }
      .site-nav .nav-link {
        font-size: .82rem;
        padding: .5rem .55rem;
      }
      .site-nav .navbar-nav {
        gap: 2px;
        justify-content: flex-start;
        width: 100%;
      }
    }

    /* ── Hero ── */
    .hero {
      background: linear-gradient(135deg, #FF6B35 0%, #FF9A5C 50%, #FFB347 100%);
      color: #fff;
      text-align: center;
      padding: 18px 24px 16px;
    }
    .hero h1 {
      font-size: 1.4rem;
      font-weight: 900;
      margin-bottom: 2px;
      letter-spacing: -0.5px;
      text-shadow: 0 2px 8px rgba(0,0,0,.15);
    }
    .hero p { color: rgba(255,255,255,.88); font-size: .82rem; margin: 0; }

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
      max-height: calc(100vh - 90px);
      overflow-y: auto;
      padding-left: 4px;
      scrollbar-width: thin;
      scrollbar-color: #D1D1D6 transparent;
    }
    .filter-sidebar::-webkit-scrollbar { width: 6px; }
    .filter-sidebar::-webkit-scrollbar-track { background: transparent; }
    .filter-sidebar::-webkit-scrollbar-thumb { background: #D1D1D6; border-radius: 3px; }
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
      border-radius: 12px;
      padding: 12px 12px 10px;
      margin-bottom: 10px;
      box-shadow: 0 1px 6px rgba(0,0,0,.06);
    }
    .filter-section-title {
      font-size: .7rem;
      font-weight: 800;
      color: #AEAEB2;
      text-transform: uppercase;
      letter-spacing: .8px;
      margin-bottom: 8px;
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
    .filter-chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .chip {
      background: #F2F2F7;
      color: #3A3A3C;
      border: none;
      border-radius: 7px;
      padding: 5px 10px;
      font-family: 'Heebo', sans-serif;
      font-size: .8rem;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
      transition: background .15s, color .15s;
      white-space: nowrap;
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
    .ship-badge {
      display: inline-block;
      font-size: .72rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      margin-top: 6px;
      white-space: nowrap;
    }
    .ship-free { background: #E8F5E9; color: #2E7D32; }
    .ship-49   { background: #FFF3E0; color: #E65100; }
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
      margin-bottom: 6px;
    }
    .detail-meta .price-tag {
      font-size: 1.25rem;
      font-weight: 800;
      color: #1C1C1E;
    }
    .price-note-row {
      text-align: right;
      margin-bottom: 18px;
    }
    .price-note {
      font-size: .72rem;
      color: #999;
      font-weight: 400;
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
      margin-bottom: 8px;
    }
    #desc-text.collapsed {
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .desc-toggle {
      background: none;
      border: none;
      color: #FF6B35;
      font-size: .88rem;
      font-weight: 600;
      cursor: pointer;
      padding: 2px 0 20px;
      display: block;
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
      margin-bottom: 28px;
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
    .footer-social {
      display: flex;
      justify-content: center;
      gap: 14px;
      margin-bottom: 14px;
    }
    .footer-social a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: #fff;
      color: #FF6B35;
      box-shadow: 0 2px 4px rgba(0,0,0,.06);
      transition: transform .15s, background .15s, color .15s;
    }
    .footer-social a:hover {
      background: #FF6B35;
      color: #fff;
      transform: translateY(-2px);
      text-decoration: none;
    }

    /* ── Mobile filter drawer ── */
    .filter-toggle-bar { display: none; }
    .filter-apply-bar  { display: none; }  /* unused — kept for safety */
    .mobile-search     { display: none; }
    @media (max-width: 767px) {
      .filter-toggle-bar {
        display: flex;
        gap: 10px;
        align-items: stretch;
        padding: 10px;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,.06);
        margin-bottom: 14px;
      }
      .filter-toggle-btn {
        background: #FF6B35;
        color: #fff;
        border: none;
        padding: 0 18px;
        border-radius: 8px;
        font-weight: 700;
        font-size: .9rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
      }
      .mobile-search {
        display: block;
        flex: 1;
        position: relative;
      }
      .mobile-search input {
        width: 100%;
        height: 100%;
        padding: 8px 36px 8px 12px;
        border-radius: 8px;
        border: 1.5px solid #E5E5EA;
        font-family: 'Heebo', sans-serif;
        font-size: .9rem;
        outline: none;
        background: #F7F7F7;
      }
      .mobile-search input:focus {
        border-color: #FF6B35;
        background: #fff;
      }
      .filter-toggle-count {
        display: none;
      }
      .filter-sidebar {
        position: fixed !important;
        top: 0;
        right: -100%;
        width: 88%;
        max-width: 360px;
        height: 100vh;
        background: #F7F7F7;
        z-index: 1050;
        overflow-y: auto;
        padding: 16px 16px 24px;
        transition: right .25s ease;
        box-shadow: -4px 0 14px rgba(0,0,0,.15);
      }
      .filter-sidebar.open { right: 0; }
      .filter-backdrop {
        display: none;
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,.4);
        z-index: 1040;
      }
      .filter-backdrop.open { display: block; }
      .filter-close {
        background: none;
        border: none;
        font-size: 1.4rem;
        color: #1C1C1E;
        cursor: pointer;
        float: left;
        line-height: 1;
        padding: 0;
        margin-bottom: 8px;
      }
      .filter-apply-btn {
        margin-top: 16px;
      }
      .filter-apply-btn {
        width: 100%;
        background: #FF6B35;
        color: #fff;
        border: none;
        padding: 13px 16px;
        border-radius: 10px;
        font-family: 'Heebo', sans-serif;
        font-weight: 700;
        font-size: 1rem;
        cursor: pointer;
        transition: background .15s;
      }
      .filter-apply-btn:hover { background: #FF5722; }
    }
  </style>
"""


def nav_html(active: str = "products", depth: str = "") -> str:
    links = [
        ("products", f"{depth}index.html",  "עמוד מוצרים"),
        ("contact",  f"{depth}contact.html", "צור קשר"),
        ("terms",    f"{depth}terms.html",   "תנאי שימוש"),
    ]
    items = ""
    for key, href, label in links:
        cls = "nav-link active" if key == active else "nav-link"
        items += f'<li class="nav-item"><a class="{cls}" href="{href}">{label}</a></li>'

    return f"""
<nav class="navbar navbar-expand site-nav">
  <div class="container">
    <a class="navbar-brand" href="{depth}index.html">Top Picks</a>
    <ul class="navbar-nav me-auto">
      {items}
    </ul>
  </div>
</nav>"""


def footer_html(depth: str = "") -> str:
    return f"""
<footer class="site-footer">
  <div class="footer-social">
    <a href="https://www.tiktok.com/@toppickproducts7" target="_blank" rel="noopener" aria-label="TikTok" title="TikTok">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1.84-.1z"/></svg>
    </a>
    <a href="https://www.instagram.com/" target="_blank" rel="noopener" aria-label="Instagram" title="Instagram">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
    </a>
    <a href="mailto:toppickp@gmail.com" aria-label="Email" title="toppickp@gmail.com">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
    </a>
  </div>
  <p class="mb-1">Top Picks · מוצרי אמזון מובחרים לשלוח לישראל 🇮🇱</p>
  <p class="mb-0"><a href="{depth}terms.html">תנאי שימוש</a> · <a href="{depth}contact.html">צור קשר</a></p>
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

        ship_type = p.get("free_shipping_type") or ""
        if ship_type == "free":
            ship_badge = '<span class="ship-badge ship-free">🚚 משלוח חינם</span>'
        elif ship_type == "free_over_49":
            ship_badge = '<span class="ship-badge ship-49">🚚 חינם בקנייה +$49</span>'
        else:
            ship_badge = ""

        cards += f"""
    <a class="product-card" href="products/{asin}.html"
       data-price="{price}" data-rating="{rating}" data-category="{cat}" data-ship="{ship_type}" data-name="{name_he[:80].lower()}">
      {cat_badge}
      <img class="card-img" src="{img}" alt="{name_he[:60]}" loading="lazy"
           onerror="this.src='{PLACEHOLDER_SVG}'">
      <div class="card-body">
        <div class="card-name">{name_he[:70]}</div>
        <div class="card-meta">
          <span class="badge-rating">{rating_str}</span>
          <span class="card-price">{price_str}</span>
        </div>
        {ship_badge}
      </div>
    </a>"""

    count = len(products)

    sidebar = f"""
    <aside class="filter-sidebar" id="filter-sidebar">
      <button class="filter-close d-md-none" onclick="closeFilterDrawer()" aria-label="סגור">✕</button>
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
        <div class="filter-section-title">משלוח</div>
        <div class="filter-chips" id="ship-chips">
          <button class="chip active" data-ship=""              onclick="setShip(this)">הכל</button>
          <button class="chip"        data-ship="free"          onclick="setShip(this)">🚚 משלוח חינם</button>
          <button class="chip"        data-ship="free_over_49"  onclick="setShip(this)">חינם בקנייה +$49</button>
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
      <button class="filter-apply-btn d-md-none" onclick="closeFilterDrawer()" id="filter-apply-btn">הצג {count} מוצרים</button>
    </aside>"""

    filter_js = """
<script>
  let activePrice  = 99999;
  let activeRating = 0;
  let activeCat    = "";
  let activeShip   = "";

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
      const ship   = c.dataset.ship || "";
      const name   = c.dataset.name || "";
      const show   = price <= activePrice
                  && rating >= activeRating
                  && (activeCat === "" || cat === activeCat)
                  && (activeShip === "" || ship === activeShip)
                  && (query === "" || name.includes(query));
      c.style.display = show ? "" : "none";
      if (show) visible++;
    });
    const total = cards.length;
    const txt = visible === total ? `${total} מוצרים` : `${visible} מתוך ${total}`;
    document.getElementById("results-count").textContent = txt;
    const applyBtn = document.getElementById("filter-apply-btn");
    if (applyBtn) applyBtn.textContent = `הצג ${visible} מוצרים`;
    saveFilterState();
  }

  function onMobileSearchInput() {
    const v = document.getElementById("mobile-search-input").value || "";
    document.getElementById("search-input").value = v;
    applyFilters();
  }

  function saveFilterState() {
    const state = {
      price: activePrice,
      rating: activeRating,
      cat: activeCat,
      ship: activeShip,
      query: document.getElementById("search-input").value || ""
    };
    sessionStorage.setItem("productGridFilters", JSON.stringify(state));
  }

  function restoreFilterState() {
    const raw = sessionStorage.getItem("productGridFilters");
    if (!raw) return false;
    try {
      const s = JSON.parse(raw);
      if (s.query) {
        document.getElementById("search-input").value = s.query;
        const m = document.getElementById("mobile-search-input");
        if (m) m.value = s.query;
      }
      if (s.price !== undefined) {
        document.querySelectorAll("#price-chips .chip").forEach(b => {
          b.classList.toggle("active", parseFloat(b.dataset.max) === s.price);
        });
        activePrice = s.price;
      }
      if (s.rating !== undefined) {
        document.querySelectorAll("#rating-chips .chip").forEach(b => {
          b.classList.toggle("active", parseFloat(b.dataset.min) === s.rating);
        });
        activeRating = s.rating;
      }
      if (s.cat !== undefined) {
        document.querySelectorAll("#cat-chips .chip").forEach(b => {
          b.classList.toggle("active", (b.dataset.cat || "") === s.cat);
        });
        activeCat = s.cat;
      }
      if (s.ship !== undefined) {
        document.querySelectorAll("#ship-chips .chip").forEach(b => {
          b.classList.toggle("active", (b.dataset.ship || "") === s.ship);
        });
        activeShip = s.ship;
      }
      return true;
    } catch (e) { return false; }
  }

  function openFilterDrawer() {
    document.getElementById("filter-sidebar").classList.add("open");
    document.getElementById("filter-backdrop").classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function closeFilterDrawer() {
    document.getElementById("filter-sidebar").classList.remove("open");
    document.getElementById("filter-backdrop").classList.remove("open");
    document.body.style.overflow = "";
    window.scrollTo({ top: 0, behavior: "smooth" });
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
  function setShip(btn) {
    document.querySelectorAll("#ship-chips .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeShip = btn.dataset.ship || "";
    applyFilters();
  }

  document.addEventListener("DOMContentLoaded", () => {
    // Restore filter state if returning from a product page
    const fromProduct = sessionStorage.getItem("productGridScroll") !== null;
    if (fromProduct) restoreFilterState();
    applyFilters();

    // Restore scroll position when returning from a product page
    const savedScroll = sessionStorage.getItem("productGridScroll");
    if (savedScroll !== null) {
      sessionStorage.removeItem("productGridScroll");
      sessionStorage.removeItem("productGridFilters");
      requestAnimationFrame(() => {
        window.scrollTo({ top: parseInt(savedScroll, 10), behavior: "instant" });
      });
    }

    // Save scroll position before navigating to a product page
    document.querySelectorAll(".product-card").forEach(card => {
      card.addEventListener("click", () => {
        sessionStorage.setItem("productGridScroll", window.scrollY);
        saveFilterState();
      });
    });
  });
</script>"""

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("Top Picks — מוצרים מנצחים")}
<body>
{nav_html("products")}

<div class="hero">
  <h1>Top Picks 🇮🇱</h1>
  <p>{count} מוצרים מאמאזון · משלוח לישראל</p>
</div>

<div class="container">
  <div class="filter-toggle-bar">
    <button class="filter-toggle-btn" onclick="openFilterDrawer()">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
      סינון
    </button>
    <div class="mobile-search">
      <input type="text" id="mobile-search-input" placeholder="🔍 חיפוש מוצר..." oninput="onMobileSearchInput()" autocomplete="off">
    </div>
  </div>
  <div class="filter-backdrop" id="filter-backdrop" onclick="closeFilterDrawer()"></div>
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
    price_note_row = f'<div class="price-note-row"><span class="price-note">נבדק {updated_label} · המחיר עשוי להשתנות</span></div>' if updated_label else ""
    ship_type = p.get("free_shipping_type") or ""
    if ship_type == "free":
        detail_ship_badge = '<div style="margin-bottom:16px;"><span class="ship-badge ship-free">🚚 משלוח חינם</span></div>'
    elif ship_type == "free_over_49":
        detail_ship_badge = '<div style="margin-bottom:16px;"><span class="ship-badge ship-49">🚚 חינם בקנייה +$49</span></div>'
    else:
        detail_ship_badge = ""
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
      {f'<span class="price-tag">{price_str}</span>' if price_str else ""}
    </div>
    {price_note_row}"""

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html(f"{name[:50]} — Top Picks")}
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
  {detail_ship_badge}
  <hr class="divider">

  <a class="buy-btn" href="{affiliate}" target="_blank" rel="noopener noreferrer">
    🛒&nbsp; רכישה באמזון
  </a>

  <div class="desc-wrap">
    <p class="detail-desc" id="desc-text">{desc_he}</p>
    <button class="desc-toggle" id="desc-toggle" onclick="toggleDesc()">הצג עוד ▾</button>
  </div>

  <script>
    function toggleDesc() {{
      var el = document.getElementById("desc-text");
      var btn = document.getElementById("desc-toggle");
      if (el.classList.contains("collapsed")) {{
        el.classList.remove("collapsed");
        btn.textContent = "הצג פחות ▴";
        el.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
      }} else {{
        el.classList.add("collapsed");
        btn.textContent = "הצג עוד ▾";
      }}
    }}
    document.addEventListener("DOMContentLoaded", function() {{
      var el = document.getElementById("desc-text");
      var btn = document.getElementById("desc-toggle");
      if (el && el.scrollHeight > el.clientHeight + 10) {{
        el.classList.add("collapsed");
        btn.style.display = "block";
      }} else if (btn) {{
        btn.style.display = "none";
      }}
    }});
  </script>

  {f'''<div class="tiktok-wrap">
    <iframe src="https://www.tiktok.com/embed/v2/{tiktok_video_id}"
            allowfullscreen allow="autoplay; encrypted-media">
    </iframe>
  </div>''' if tiktok_video_id else ""}
</div>

{footer_html(depth="../")}
{BOOTSTRAP_JS}
</body>
</html>"""


# ── Static pages ───────────────────────────────────────────────────────────

def build_about() -> str:
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("עלינו — Top Picks")}
<body>
{nav_html("about")}
<div class="static-page">
  <div class="static-card">
    <h1>עלינו</h1>
    <div class="wip-badge">⏳ עמוד בבנייה — תוכן יתווסף בקרוב</div>
    <p>
      ברוכים הבאים ל<strong>Top Picks</strong> — המקום שבו תמצאו את מיטב
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
{head_html("צור קשר — Top Picks")}
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
{head_html("תנאי שימוש — Top Picks")}
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
    raw = [p for p in get_all() if p["status"] in ("ready_for_video", "video_ready", "video_failed")]

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
            "free_shipping_type": p.get("free_shipping_type") or "",
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
    (DOCS / "contact.html").write_text(build_contact(), encoding="utf-8")
    (DOCS / "terms.html").write_text(build_terms(),   encoding="utf-8")
    # Remove orphaned about.html (no longer in nav)
    about_path = DOCS / "about.html"
    if about_path.exists():
        about_path.unlink()
    print("✓ docs/contact.html  docs/terms.html")

    print("\nDone! Push with:")
    print("  git add docs/ && git commit -m 'Update products' && git push")


if __name__ == "__main__":
    build()
