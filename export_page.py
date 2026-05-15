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
      padding: 56px 24px 48px;
    }
    .hero h1 {
      font-size: 2.2rem;
      font-weight: 900;
      margin-bottom: .5rem;
      letter-spacing: -0.5px;
      text-shadow: 0 2px 8px rgba(0,0,0,.15);
    }
    .hero p { color: rgba(255,255,255,.88); font-size: 1.05rem; margin: 0; }

    /* ── Product grid ── */
    .product-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
      padding: 32px 0;
    }
    @media (max-width: 991px) {
      .product-grid { grid-template-columns: repeat(3, 1fr); }
    }
    @media (max-width: 767px) {
      .product-grid { grid-template-columns: repeat(2, 1fr); gap: 14px; }
    }
    @media (max-width: 479px) {
      .product-grid { grid-template-columns: 1fr; }
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
      height: 220px;
      object-fit: contain;
      background: #F2F2F7;
      padding: 12px;
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

def build_index(products: list[dict]) -> str:
    cards = ""
    for p in products:
        img = p.get("image_url") or PLACEHOLDER_SVG
        name = (p.get("name") or p["asin"]).replace('"', "&quot;")
        name_short = name[:80]
        rating_str = f"⭐ {p['rating']:.1f}" if p.get("rating") else "—"
        price_str  = f"${p['price']:.2f}"   if p.get("price") else "—"
        cat        = (p.get("category") or "").replace('"', "&quot;")
        cat_badge  = f'<span class="category-badge">{cat[:20]}</span>' if cat and cat != "—" else ""
        asin       = p["asin"]

        cards += f"""
    <a class="product-card" href="products/{asin}.html">
      {cat_badge}
      <img class="card-img" src="{img}" alt="{name_short}" loading="lazy"
           onerror="this.src='{PLACEHOLDER_SVG}'">
      <div class="card-body">
        <div class="card-name">{name_short}</div>
        <div class="card-meta">
          <span class="badge-rating">{rating_str}</span>
          <span class="card-price">{price_str}</span>
        </div>
      </div>
    </a>"""

    count = len(products)
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("המוצרים שלי — מוצרים מנצחים")}
<body>
{nav_html("products")}

<div class="hero">
  <h1>מוצרים מנצחים לשלוח לישראל 🇮🇱</h1>
  <p>{count} מוצרים מאומזון · משלוח לישראל</p>
</div>

<div class="container">
  <div class="product-grid">
    {cards}
  </div>
</div>

{footer_html()}
{BOOTSTRAP_JS}
</body>
</html>"""


# ── Product detail page ────────────────────────────────────────────────────

def build_product_page(p: dict) -> str:
    asin         = p["asin"]
    name         = (p.get("name") or asin).replace('"', "&quot;")
    img          = p.get("image_url") or PLACEHOLDER_SVG
    rating_str   = f"⭐ {p['rating']:.1f}" if p.get("rating") else ""
    reviews_str  = f"({p['reviews']:,} ביקורות)" if p.get("reviews") else ""
    price_str    = f"${p['price']:.2f}" if p.get("price") else ""
    affiliate    = p.get("link") or f"https://www.amazon.com/dp/{asin}/?tag=eskl20-20"
    desc_he      = p.get("description_he") or "תיאור המוצר יתעדכן בקרוב."

    rating_block = ""
    if rating_str or price_str:
        rating_block = f"""
    <div class="detail-meta">
      {f'<span class="badge-rating">{rating_str}</span>' if rating_str else ""}
      {f'<span class="reviews-count">{reviews_str}</span>' if reviews_str else ""}
      {f'<span class="price-tag">{price_str}</span>' if price_str else ""}
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
    <div class="wip-badge">⏳ עמוד בבנייה — תוכן יתווסף בקרוב</div>
    <p>
      יש לכם שאלה, הצעה, או מוצר שאתם רוצים שנוסיף? נשמח לשמוע!
    </p>
    <p>
      ניתן לפנות אלינו בדוא"ל: <a href="mailto:cohenesther003@gmail.com">cohenesther003@gmail.com</a>
    </p>
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
    <div class="wip-badge">⏳ עמוד בבנייה — תוכן יתווסף בקרוב</div>
    <p>
      האתר כולל קישורי שותפים (Affiliate Links) לאמזון. עמלה עשויה להתקבל על
      רכישות שבוצעו דרך קישורים אלה, ללא עלות נוספת לרוכש.
    </p>
    <p>
      המוצרים, המחירים וזמינות המשלוח מתעדכנים באופן שוטף ישירות מאמזון.
      אנו ממליצים לאמת פרטים לפני ביצוע רכישה.
    </p>
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
            "asin":         p["asin"],
            "name":         p.get("name") or p["asin"],
            "category":     p.get("category") or "—",
            "rating":       round(p.get("rating") or 0, 1),
            "price":        round(p.get("price_usd") or 0, 2),
            "reviews":      p.get("review_count") or 0,
            "link":         p.get("affiliate_link") or f"https://www.amazon.com/dp/{p['asin']}/?tag=eskl20-20",
            "image_url":    p.get("image_url") or "",
            "description_he": p.get("description_he") or "",
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
