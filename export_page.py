"""
Generates the full public site in docs/:
  docs/index.html              — Hebrew RTL product grid
  docs/products/{asin}.html   — individual product detail pages
  docs/contact.html           — Contact page (Hebrew stub)
  docs/terms.html             — Terms of Use page (Hebrew stub)

Run: python export_page.py
Then: git add docs/ && git commit -m "Update products" && git push
"""

import html as _html
import re
from pathlib import Path
from src.db import init_db, get_all

DOCS = Path(__file__).parent / "docs"
PRODUCTS_DIR = DOCS / "products"

GOOGLE_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
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

      background: #0f172a;
      font-family: 'Heebo', 'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif;
      color: #f1f5f9;
      margin: 0;
    }

    /* ── Navbar ── */
    .site-nav {

      background: #1e293b;
      padding: 0 1.25rem;
      position: sticky;
      top: 0;
      z-index: 1000;
      box-shadow: 0 1px 0 #334155;
      border-bottom: 1px solid #334155;
      min-height: 48px;
    }
    .site-nav .navbar {
      padding-top: 6px;
      padding-bottom: 6px;
    }
    .site-nav .navbar-brand {
      font-family: 'Plus Jakarta Sans', 'Heebo', sans-serif;
      font-size: 1.2rem;
      font-weight: 800;
      background: linear-gradient(90deg, #f59e0b, #fbbf24);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.3px;
      margin: 0;
    }
    .site-nav .nav-link {
      color: #94a3b8 !important;
      font-weight: 600;
      font-size: .9rem;
      padding: .55rem .8rem;
      transition: color .15s;
    }
    .site-nav .nav-link:hover,
    .site-nav .nav-link.active {
      color: #f59e0b !important;
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
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      color: #fff;
      text-align: center;
      padding: 18px 24px 16px;
    }
    .hero h1 {
      font-family: 'Plus Jakarta Sans', 'Heebo', sans-serif;
      font-size: 1.4rem;
      font-weight: 800;
      margin-bottom: 2px;
      letter-spacing: -0.5px;
      background: linear-gradient(90deg, #f59e0b, #fbbf24);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .hero p { color: #94a3b8; font-size: .82rem; margin: 0; }

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
      scrollbar-color: #334155 transparent;
    }
    .filter-sidebar::-webkit-scrollbar { width: 6px; }
    .filter-sidebar::-webkit-scrollbar-track { background: transparent; }
    .filter-sidebar::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    .filter-sidebar h2 {
      font-size: .7rem;
      font-weight: 800;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin: 0 0 16px;
    }
    .filter-section {

      background: #1e293b;
      border-radius: 14px;
      padding: 12px 12px 10px;
      margin-bottom: 10px;
      border: 1px solid #334155;
      box-shadow: 0 1px 3px rgba(0,0,0,.2);
    }
    .filter-section-title {
      font-size: .7rem;
      font-weight: 800;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: .8px;
      margin-bottom: 8px;
    }
    .search-wrap { position: relative; }
    .search-inner { position: relative; display: flex; align-items: center; }
    .search-box {
      width: 100%;
      border: 1.5px solid #334155;
      border-radius: 10px;
      padding: 9px 36px 9px 12px;
      font-family: 'Heebo', sans-serif;
      font-size: .9rem;
      outline: none;
      direction: rtl;
      transition: border-color .15s;
      background: #0f172a;
    }
    .search-box:focus { border-color: #f59e0b; background: #1e293b; }
    .search-clear {
      position: absolute;
      left: 10px;
      background: none;
      border: none;
      cursor: pointer;
      color: #64748b;
      font-size: 1rem;
      line-height: 1;
      padding: 2px;
      display: none;
    }
    .search-clear:hover { color: #f59e0b; }
    .search-suggestions {
      display: none;
      position: absolute;
      top: calc(100% + 4px);
      right: 0; left: 0;
      background: #1e293b;
      border: 1.5px solid #334155;
      border-radius: 10px;
      box-shadow: 0 4px 16px rgba(0,0,0,.35);
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
      border-bottom: 1px solid #334155;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: #f1f5f9;
    }
    .suggestion-item:last-child { border-bottom: none; }
    .suggestion-item:hover, .suggestion-item.active { background: rgba(245,158,11,0.12); color: #f59e0b; }
    .suggestion-item mark { background: none; color: #f59e0b; font-weight: 700; }
    .filter-chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .chip {

      background: #334155;
      color: #94a3b8;
      border: none;
      border-radius: 8px;
      padding: 5px 10px;
      font-family: 'Heebo', sans-serif;
      font-size: .8rem;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
      transition: background .15s, color .15s;
      white-space: nowrap;
    }
    .chip:hover { background: #ffe8df; color: #f59e0b; }
    .chip.active { background: #f59e0b; color: #0f172a; }
    #results-count {
      font-size: .78rem;
      color: #64748b;
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

      .product-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
    }

    @media (max-width: 479px) {
      .product-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .no-results {
      text-align: center;
      padding: 60px 20px;
      color: #64748b;
      font-size: 1rem;
      display: none;
      grid-column: 1/-1;
    }

    /* ── Product card ── */
    .product-card {

      background: #1e293b;
      border-radius: 16px;
      border: 1px solid #334155;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,.25);
      cursor: pointer;
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      transition: transform .22s ease, box-shadow .22s ease;
      position: relative;
    }
    .product-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 24px rgba(0,0,0,.35);
      color: inherit;
      text-decoration: none;
    }
    .product-card .card-img {
      width: 100%;
      height: 260px;
      object-fit: contain;

      background: #263147;
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
      color: #f1f5f9;
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
      border-radius: 20px;
      margin-top: 6px;
      white-space: nowrap;
    }

    .ship-free  { background: rgba(34,197,94,0.15); color: #4ade80; }
    .ship-49    { background: rgba(245,158,11,0.15); color: #fbbf24; }
    .ship-prime { background: rgba(96,165,250,0.15); color: #60a5fa; }
    .badge-rating {
      background: rgba(245,158,11,0.15);
      color: #fbbf24;
      font-size: .78rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 20px;
    }
    .card-price {
      font-size: .9rem;
      font-weight: 700;
      color: #4ade80;
    }
    .category-badge {
      position: absolute;
      top: 10px;
      left: 10px;
      background: rgba(245,158,11,0.85);
      color: #fff;
      font-size: .68rem;
      font-weight: 700;
      padding: 3px 9px;
      border-radius: 20px;
      letter-spacing: .3px;
      text-transform: uppercase;
      backdrop-filter: blur(4px);
    }

    /* ── Three-dots share button ── */
    .share-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: rgba(15,23,42,0.72);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      border: none;
      color: #f1f5f9;
      font-size: 1.1rem;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      z-index: 10;
      transition: background .15s, transform .1s;
      letter-spacing: 1px;
    }
    .share-btn:hover { background: rgba(245,158,11,0.85); color: #0f172a; }

    /* ── Share sheet (bottom modal) ── */
    .share-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.65);
      z-index: 2000;
    }
    .share-overlay.open { display: block; }
    .share-sheet {
      position: fixed;
      bottom: -100%;
      left: 0; right: 0;
      background: #1e293b;
      border-radius: 24px 24px 0 0;
      border-top: 1px solid #334155;
      padding: 16px 20px 36px;
      z-index: 2001;
      transition: bottom .32s cubic-bezier(.25,.8,.25,1);
      max-height: 90vh;
      overflow-y: auto;
    }
    .share-sheet.open { bottom: 0; }
    .sheet-handle {
      width: 40px; height: 4px;
      border-radius: 2px;
      background: #475569;
      margin: 0 auto 20px;
    }
    .sheet-product {
      display: flex;
      align-items: center;
      gap: 14px;
      background: #263147;
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 20px;
      border: 1px solid #334155;
    }
    .sheet-product-img {
      width: 72px; height: 72px;
      border-radius: 10px;
      object-fit: cover;
      background: #334155;
      flex-shrink: 0;
    }
    .sheet-product-info { flex: 1; min-width: 0; }
    .sheet-product-name {
      font-size: .9rem;
      font-weight: 700;
      color: #f1f5f9;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      line-height: 1.35;
      margin-bottom: 4px;
      direction: rtl;
    }
    .sheet-product-url {
      font-size: .72rem;
      color: #64748b;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      direction: ltr;
    }
    .share-actions {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-bottom: 16px;
    }
    .share-action-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      background: #263147;
      border: 1px solid #334155;
      border-radius: 14px;
      padding: 14px 8px 12px;
      cursor: pointer;
      transition: background .15s, border-color .15s;
      color: #f1f5f9;
      font-family: 'Heebo', sans-serif;
      font-size: .72rem;
      font-weight: 600;
    }
    .share-action-btn:hover { background: rgba(245,158,11,0.1); border-color: #f59e0b; color: #f59e0b; }
    .share-action-btn svg { width: 26px; height: 26px; }
    .share-buy-btn {
      display: block;
      width: 100%;
      background: #22c55e;
      color: #fff;
      font-family: 'Heebo', 'Plus Jakarta Sans', sans-serif;
      font-size: 1rem;
      font-weight: 700;
      padding: 14px 32px;
      border-radius: 50px;
      border: none;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
      box-shadow: 0 4px 16px rgba(34,197,94,0.28);
      transition: background .15s, transform .1s;
    }
    .share-buy-btn:hover { background: #16a34a; color: #fff; text-decoration: none; }
    .share-copy-toast {
      position: fixed;
      bottom: 100px;
      left: 50%;
      transform: translateX(-50%) translateY(20px);
      background: #22c55e;
      color: #fff;
      padding: 10px 20px;
      border-radius: 50px;
      font-size: .88rem;
      font-weight: 600;
      opacity: 0;
      transition: opacity .2s, transform .2s;
      z-index: 3000;
      pointer-events: none;
    }
    .share-copy-toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

    /* ── Floating clear-filters pill (visible while scrolling) ── */
    .floating-clear-btn {
      position: fixed;
      bottom: 28px;
      left: 50%;
      transform: translateX(-50%) translateY(90px);
      background: #f59e0b;
      color: #0f172a;
      border: none;
      border-radius: 50px;
      padding: 13px 26px;
      font-family: 'Heebo', 'Plus Jakarta Sans', sans-serif;
      font-weight: 800;
      font-size: .92rem;
      cursor: pointer;
      z-index: 900;
      box-shadow: 0 6px 24px rgba(0,0,0,0.45);
      transition: transform .3s cubic-bezier(.34,1.56,.64,1), opacity .25s;
      opacity: 0;
      pointer-events: none;
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 8px;
      letter-spacing: .1px;
    }
    .floating-clear-btn.visible {
      transform: translateX(-50%) translateY(0);
      opacity: 1;
      pointer-events: auto;
    }
    .floating-clear-btn:hover { background: #d97706; }
    .floating-clear-btn:active { transform: translateX(-50%) scale(.96); }

    /* ── Clear filters button (sidebar) ── */
    .sidebar-clear-btn {
      display: none;
      width: 100%;
      margin-top: 8px;
      padding: 9px 14px;
      background: rgba(245,158,11,0.1);
      color: #f59e0b;
      border: 1px solid rgba(245,158,11,0.25);
      border-radius: 50px;
      font-family: 'Heebo', sans-serif;
      font-weight: 700;
      font-size: .82rem;
      cursor: pointer;
      text-align: center;
      transition: background .15s;
    }
    .sidebar-clear-btn.visible { display: block; }
    .sidebar-clear-btn:hover { background: rgba(245,158,11,0.2); }

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
      color: #94a3b8;
      text-decoration: none;
      font-size: .9rem;
      margin-bottom: 24px;
      transition: color .15s;
    }
    .back-link:hover { color: #f59e0b; }
    .detail-img-wrap {

      background: #263147;
      border-radius: 20px;
      border: 1px solid #334155;
      padding: 24px;
      text-align: center;
      margin-bottom: 28px;
      box-shadow: 0 2px 8px rgba(0,0,0,.25);
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
      color: #f1f5f9;
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
      color: #4ade80;
    }
    .price-note-row {
      text-align: right;
      margin-bottom: 18px;
    }
    .price-note {
      font-size: .72rem;
      color: #64748b;
      font-weight: 400;
    }
    .detail-meta .reviews-count {
      color: #94a3b8;
      font-size: .88rem;
    }
    .divider { border: none; border-top: 1px solid #334155; margin: 20px 0; }
    .detail-desc {
      font-size: 1rem;
      line-height: 1.85;
      color: #cbd5e1;
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
      color: #f59e0b;
      font-size: .88rem;
      font-weight: 600;
      cursor: pointer;
      padding: 2px 0 20px;
      display: block;
    }
    .buy-btn {
      display: block;
      width: 100%;
      background: #22c55e;
      color: #fff;
      font-family: 'Heebo', 'Plus Jakarta Sans', sans-serif;
      font-size: 1.1rem;
      font-weight: 700;
      padding: 16px 32px;
      border-radius: 50px;
      border: none;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
      box-shadow: 0 4px 20px rgba(34,197,94,0.30);
      transition: background .15s, transform .1s, box-shadow .15s;
      margin-bottom: 28px;
      letter-spacing: .2px;
    }
    .buy-btn:hover {
      background: #16a34a;
      color: #fff;
      transform: translateY(-2px);
      box-shadow: 0 8px 28px rgba(34,197,94,0.35);
      text-decoration: none;
    }
    .buy-btn:active { transform: translateY(0); box-shadow: 0 2px 8px rgba(34,197,94,0.25); }
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
      background: #1e293b;
      border-radius: 20px;
      border: 1px solid #334155;
      padding: 40px 36px;
      box-shadow: 0 2px 8px rgba(0,0,0,.25);
      line-height: 1.85;
    }
    .static-card h1 { font-size: 1.6rem; font-weight: 800; margin-bottom: 20px; color: #f1f5f9; }
    .static-card p { color: #cbd5e1; }
    .wip-badge {
      display: inline-block;
      background: rgba(245,158,11,0.15);
      color: #fbbf24;
      border-radius: 20px;
      padding: 8px 16px;
      font-size: .9rem;
      font-weight: 600;
      margin-bottom: 20px;
    }

    /* ── Footer ── */
    .site-footer {

      background: #0f172a;
      color: #64748b;
      text-align: center;
      padding: 28px 16px;
      font-size: .82rem;
      border-top: 1px solid #334155;
    }
    .site-footer a { color: #f59e0b; text-decoration: none; }
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
      background: #1e293b;
      color: #94a3b8;
      border: 1px solid #334155;
      box-shadow: 0 1px 3px rgba(0,0,0,.25);
      transition: transform .15s, background .15s, color .15s;
    }
    .footer-social a:hover {
      background: #f59e0b;
      color: #fff;
      border-color: #f59e0b;
      transform: translateY(-2px);
      text-decoration: none;
    }

    /* ── Mobile filter drawer ── */
    .filter-toggle-bar { display: none; }
    .mobile-search     { display: none; }
    @media (max-width: 767px) {
      .filter-toggle-bar {
        display: flex;
        gap: 10px;
        align-items: stretch;
        padding: 10px;
        background: #1e293b;
        border-radius: 14px;
        border: 1px solid #334155;
        box-shadow: 0 1px 3px rgba(0,0,0,.2);
        margin-bottom: 14px;
      }
      .filter-toggle-btn {
        background: #f59e0b;
        color: #0f172a;
        border: none;
        padding: 0 18px;
        border-radius: 50px;
        font-weight: 700;
        font-size: .9rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(245,158,11,0.25);
      }
      .mobile-search {
        display: block;
        flex: 1;
        position: relative;
      }
      .mobile-search input {
        width: 100%;
        height: 100%;
        padding: 8px 32px 8px 12px;
        border-radius: 50px;
        border: 1.5px solid #334155;
        font-family: 'Heebo', sans-serif;
        font-size: 16px; /* ≥16px prevents iOS Safari auto-zoom on focus */
        outline: none;
        background: #0f172a;
        color: #f1f5f9;
        -webkit-text-size-adjust: none;
      }
      .mobile-search input::placeholder { color: #64748b; }
      .mobile-search input:focus {
        border-color: #f59e0b;
        background: #1e293b;
      }
      .mobile-search-clear {
        position: absolute;
        left: 10px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: #64748b;
        font-size: .9rem;
        cursor: pointer;
        padding: 4px 6px;
        line-height: 1;
        display: none;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: color .15s;
      }
      .mobile-search-clear:hover { color: #f59e0b; }
      /* ── Active filters indicator on the filter button ── */
      .filter-active-dot {
        display: none;
        width: 7px; height: 7px;
        border-radius: 50%;
        background: #22c55e;
        margin-right: -3px;
        margin-left: 2px;
        flex-shrink: 0;
      }
      .filter-active-dot.visible { display: inline-block; }
      .filter-sidebar {
        position: fixed !important;
        top: 0;
        right: -100%;
        width: 88%;
        max-width: 360px;
        height: 100vh;
        background: #0f172a;
        z-index: 1050;
        overflow-y: auto;
        padding: 16px 16px 24px;
        transition: right .25s ease;
        box-shadow: -4px 0 14px rgba(0,0,0,.12);
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
        color: #f1f5f9;
        cursor: pointer;
        float: right;
        line-height: 1;
        padding: 0;
        margin-bottom: 8px;
      }
      .filter-apply-btn {
        margin-top: 16px;
        width: 100%;
        background: #f59e0b;
        color: #0f172a;
        border: none;
        padding: 13px 16px;
        border-radius: 50px;
        font-family: 'Heebo', sans-serif;
        font-weight: 700;
        font-size: 1rem;
        cursor: pointer;
        transition: background .15s, box-shadow .15s;
        box-shadow: 0 4px 14px rgba(245,158,11,0.28);
      }
      .filter-apply-btn:hover { background: #d97706; }
    }

    /* ── MOBILE overrides ── */
    @media (max-width: 767px) {

      /* ── Mobile nav: glass effect ── */
      .site-nav {
        background: rgba(15,23,42,0.95);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: none;
        border-bottom: 1px solid rgba(51,65,85,0.6);
      }

      /* ── Mobile hero: profile-style header ── */
      .hero {
        background: #0f172a !important;
        padding: 24px 20px 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
      }

      .hero::before {
        content: "🇮🇱";
        display: flex;
        align-items: center;
        justify-content: center;
        width: 84px;
        height: 84px;
        border-radius: 50%;
        background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
        font-size: 2.2rem;
        line-height: 1;
        margin-bottom: 14px;
        box-shadow: 0 4px 18px rgba(245,158,11,0.35);
        flex-shrink: 0;
      }
      .hero h1 {
        font-size: 1.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: none;
        margin-bottom: 4px;
      }
      .hero p {
        color: #94a3b8;
        font-size: .82rem;
        margin: 0;
      }

      /* ── Mobile filter bar ── */
      .filter-toggle-bar {
        border-radius: 50px !important;
        padding: 7px 10px !important;
        margin: 4px 0 10px !important;
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
      }
      .mobile-search input {
        border-radius: 50px;
        border: none !important;
        background: transparent !important;
        font-size: 16px; /* ≥16px prevents iOS Safari auto-zoom */
        color: #f1f5f9;
      }
      .mobile-search input:focus {
        background: transparent !important;
        border: none !important;
        box-shadow: none;
      }

      /* ── Mobile product cards: square layout ── */
      .product-card {
        border-radius: 14px;
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
      }
      .product-card:hover {
        transform: none !important;
        box-shadow: none !important;
      }

      .product-card .card-img {
        height: auto !important;
        aspect-ratio: 1 / 1;
        object-fit: cover;
        padding: 0 !important;
        background: rgba(0,0,0,0.08) !important;
        border-radius: 14px 14px 0 0;
      }

      .product-card .card-body {
        background: #1e293b;
        border-radius: 0 0 14px 14px;
        padding: 10px 10px 12px;
        gap: 2px;
        min-height: 60px;
      }

      .product-card .card-name {
        font-size: .82rem;
        font-weight: 500;
        line-height: 1.2;
        -webkit-line-clamp: 1;
        letter-spacing: -0.1px;
        color: #f1f5f9;
      }

      /* Price: small green on mobile — signals deal */
      .card-price {
        font-size: .72rem;
        font-weight: 600;
        color: #4ade80;
      }

      /* Hide badges on mobile — name + price only */
      .ship-badge { display: none !important; }
      .badge-rating { display: none !important; }

      /* Category badge: smaller */
      .category-badge {
        font-size: .58rem;
        padding: 2px 6px;
        top: 7px;
        left: 7px;
      }

      /* ── Page layout: no top margin ── */
      .page-layout {
        padding-top: 16px;
        gap: 0;
      }

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
    "top": "⭐ TOP",
    "byotools": "BYOTOOLS",
    "Best Sellers Kitchen Dining": "מטבח ואוכל",
    "Best Sellers Sports Outdoors": "ספורט וטבע",
    "Best Sellers Tools Home Improvement": "כלים ושיפוצים",
}

def build_index(products: list[dict]) -> str:
    categories = sorted({p.get("category") or "" for p in products if p.get("category")})

    cards = ""
    for p in products:
        img      = (p.get("image_url") or "").strip() or PLACEHOLDER_SVG  # guard empty string
        name_he  = _html.escape(p.get("name_he") or p.get("name") or p["asin"])
        rating   = p.get("rating") or 0
        price    = p.get("price") or 0
        cat      = p.get("category") or ""
        asin     = p["asin"]
        link     = p.get("link") or f"https://www.amazon.com/dp/{asin}/?tag=eskl20-20"
        name_he_attr = name_he  # html.escape already handles all special chars

        rating_str = f"⭐ {rating:.1f}" if rating else "—"
        price_str  = f"${price:.2f}" if price else "—"
        cat_label  = CATEGORY_LABELS.get(cat, cat[:18])
        cat_badge  = f'<span class="category-badge">{cat_label}</span>' if cat else ""

        ship_type = p.get("free_shipping_type") or ""
        if ship_type == "free":
            ship_badge = '<span class="ship-badge ship-free">🚚 משלוח חינם</span>'
        elif ship_type == "free_over_49":
            ship_badge = '<span class="ship-badge ship-49">🚚 חינם בקנייה +$49</span>'
        elif ship_type == "free_with_prime":
            ship_badge = '<span class="ship-badge ship-prime">🚚 משלוח חינם עם Prime</span>'
        else:
            ship_badge = ""

        cards += f"""
    <a class="product-card" href="products/{asin}.html"
       data-price="{price}" data-rating="{rating}" data-category="{cat}" data-ship="{ship_type}" data-name="{name_he[:80].lower()}">
      {cat_badge}
      <button class="share-btn" onclick="openShareSheet(event,this)"
        data-asin="{asin}" data-name="{name_he_attr[:70]}"
        data-img="{img}" data-link="{link}" aria-label="שתף">&#8943;</button>
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
          <button class="chip"        data-ship="free"            onclick="setShip(this)">🚚 משלוח חינם</button>
          <button class="chip"        data-ship="free_over_49"  onclick="setShip(this)">חינם בקנייה +$49</button>
          <button class="chip"        data-ship="free_with_prime" onclick="setShip(this)">🚚 חינם עם Prime</button>
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
      <button class="sidebar-clear-btn" id="sidebar-clear-btn" onclick="clearAllFilters()">✕ נקה סינון</button>
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
    // show/hide sidebar search clear button
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
    // show/hide "clear filters" controls
    const anyFilter = activePrice < 99999 || activeRating > 0 || activeCat !== "" || activeShip !== "" || query !== "";
    const dot = document.getElementById("filter-active-dot");
    const clrBtn = document.getElementById("sidebar-clear-btn");
    const floatBtn = document.getElementById("floating-clear-btn");
    if (dot)      dot.classList.toggle("visible", anyFilter);
    if (clrBtn)   clrBtn.classList.toggle("visible", anyFilter);
    if (floatBtn) floatBtn.classList.toggle("visible", anyFilter);
    saveFilterState();
  }

  function onMobileSearchInput() {
    const v = document.getElementById("mobile-search-input").value || "";
    document.getElementById("search-input").value = v;
    const clr = document.getElementById("mobile-search-clear");
    if (clr) clr.style.display = v ? "flex" : "none";
    applyFilters();
  }

  function clearMobileSearch() {
    document.getElementById("mobile-search-input").value = "";
    document.getElementById("search-input").value = "";
    const clr = document.getElementById("mobile-search-clear");
    if (clr) clr.style.display = "none";
    closeSuggestions();
    applyFilters();
    document.getElementById("mobile-search-input").focus();
  }

  function clearAllFilters() {
    activePrice  = 99999;
    activeRating = 0;
    activeCat    = "";
    activeShip   = "";
    document.getElementById("search-input").value = "";
    const mInput = document.getElementById("mobile-search-input");
    if (mInput) mInput.value = "";
    const mClr = document.getElementById("mobile-search-clear");
    if (mClr) mClr.style.display = "none";
    document.querySelectorAll("#price-chips .chip").forEach(b =>
      b.classList.toggle("active", parseFloat(b.dataset.max) === 99999));
    document.querySelectorAll("#rating-chips .chip").forEach(b =>
      b.classList.toggle("active", parseFloat(b.dataset.min) === 0));
    document.querySelectorAll("#cat-chips .chip").forEach(b =>
      b.classList.toggle("active", (b.dataset.cat || "") === ""));
    document.querySelectorAll("#ship-chips .chip").forEach(b =>
      b.classList.toggle("active", (b.dataset.ship || "") === ""));
    closeSuggestions();
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
    <button class="filter-toggle-btn" id="filter-toggle-btn" onclick="openFilterDrawer()">
      <span class="filter-active-dot" id="filter-active-dot"></span>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
      סינון
    </button>
    <div class="mobile-search">
      <input type="text" id="mobile-search-input" placeholder="🔍 חיפוש מוצר..."
             oninput="onMobileSearchInput()" autocomplete="off" inputmode="search">
      <button class="mobile-search-clear" id="mobile-search-clear"
              onclick="clearMobileSearch()" tabindex="-1" aria-label="נקה חיפוש">✕</button>
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

<!-- Floating clear-filters pill -->
<button class="floating-clear-btn" id="floating-clear-btn" onclick="clearAllFilters()">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
  נקה סינון
</button>

{footer_html()}

<!-- Share Sheet -->
<div class="share-overlay" id="share-overlay" onclick="closeShareSheet()"></div>
<div class="share-sheet" id="share-sheet">
  <div class="sheet-handle"></div>
  <div class="sheet-product" id="sheet-product">
    <img class="sheet-product-img" id="sheet-img" src="" alt="">
    <div class="sheet-product-info">
      <div class="sheet-product-name" id="sheet-name"></div>
      <div class="sheet-product-url" id="sheet-url"></div>
    </div>
  </div>
  <div class="share-actions">
    <button class="share-action-btn" onclick="shareAction('copy')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      העתק קישור
    </button>
    <button class="share-action-btn" onclick="shareAction('whatsapp')">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M11.999 2C6.477 2 2 6.477 2 12c0 1.99.576 3.868 1.578 5.44L2 22l4.664-1.546A9.96 9.96 0 0 0 12 22c5.523 0 10-4.477 10-10S17.523 2 12 2z"/></svg>
      WhatsApp
    </button>
    <button class="share-action-btn" onclick="shareAction('facebook')">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
      Facebook
    </button>
    <button class="share-action-btn" onclick="shareAction('twitter')">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.816l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
      X / Twitter
    </button>
  </div>
  <a class="share-buy-btn" id="sheet-buy-btn" href="#" target="_blank" rel="noopener noreferrer">
    🛒&nbsp; רכישה באמזון
  </a>
</div>
<div class="share-copy-toast" id="share-copy-toast">✓ הקישור הועתק!</div>

{BOOTSTRAP_JS}
{filter_js}
<script>
  let sheetLink = "";
  function openShareSheet(e, btn) {{
    e.preventDefault();
    e.stopPropagation();
    sheetLink = btn.dataset.link || "";
    document.getElementById("sheet-img").src = btn.dataset.img || "";
    document.getElementById("sheet-name").textContent = btn.dataset.name || "";
    document.getElementById("sheet-url").textContent = "amazon.com/dp/" + (btn.dataset.asin || "");
    document.getElementById("sheet-buy-btn").href = sheetLink;
    document.getElementById("share-overlay").classList.add("open");
    document.getElementById("share-sheet").classList.add("open");
    document.body.style.overflow = "hidden";
  }}
  function closeShareSheet() {{
    document.getElementById("share-overlay").classList.remove("open");
    document.getElementById("share-sheet").classList.remove("open");
    document.body.style.overflow = "";
  }}
  function shareAction(type) {{
    const name = document.getElementById("sheet-name").textContent;
    const url = sheetLink;
    if (type === "copy") {{
      const showToast = () => {{
        const t = document.getElementById("share-copy-toast");
        t.classList.add("show");
        setTimeout(() => t.classList.remove("show"), 2200);
      }};
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(url).then(showToast).catch(() => {{
          // fallback for older iOS Safari
          const el = document.createElement("textarea");
          el.value = url; el.style.position = "fixed"; el.style.opacity = "0";
          document.body.appendChild(el); el.focus(); el.select();
          try {{ document.execCommand("copy"); showToast(); }} catch(e) {{}}
          document.body.removeChild(el);
        }});
      }} else {{
        const el = document.createElement("textarea");
        el.value = url; el.style.position = "fixed"; el.style.opacity = "0";
        document.body.appendChild(el); el.focus(); el.select();
        try {{ document.execCommand("copy"); showToast(); }} catch(e) {{}}
        document.body.removeChild(el);
      }}
    }} else if (type === "whatsapp") {{
      window.open("https://wa.me/?text=" + encodeURIComponent(name + " " + url), "_blank");
    }} else if (type === "facebook") {{
      window.open("https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(url), "_blank");
    }} else if (type === "twitter") {{
      window.open("https://twitter.com/intent/tweet?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(name), "_blank");
    }}
  }}
  document.addEventListener("keydown", e => {{
    if (e.key === "Escape") closeShareSheet();
  }});
</script>
</body>
</html>"""

# ── Product detail page ────────────────────────────────────────────────────

def build_product_page(p: dict) -> str:
    asin         = p["asin"]
    name         = _html.escape(p.get("name_he") or p.get("name") or asin)
    img          = (p.get("image_url") or "").strip() or PLACEHOLDER_SVG
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
    elif ship_type == "free_with_prime":
        detail_ship_badge = '<div style="margin-bottom:16px;"><span class="ship-badge ship-prime">🚚 משלוח חינם עם Prime</span></div>'
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

def build_contact() -> str:
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
{head_html("צור קשר — Top Picks")}
<body>
{nav_html("contact")}
<div class="static-page">
  <div class="static-card">
    <h1>צור קשר</h1>
    <p style="color:#94a3b8; margin-bottom:28px;">נשמח לשמוע ממכם — שאלות, הצעות, או מוצרים שתרצו שנוסיף לאתר.</p>

    <div style="background:#263147; border-radius:14px; border:1px solid #334155; padding:24px 20px; margin-bottom:24px; text-align:center;">
      <div style="font-size:2rem; margin-bottom:10px;">✉️</div>
      <div style="font-weight:700; font-size:1rem; margin-bottom:6px;">דוא"ל</div>
      <a href="mailto:toppickp@gmail.com" style="color:#f59e0b; font-size:1.05rem; font-weight:600; text-decoration:none;">toppickp@gmail.com</a>
    </div>

    <p style="font-size:.88rem; color:#64748b; text-align:center;">אנו מגיבים תוך 1–2 ימי עסקים.</p>
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
    <p style="color:#94a3b8; font-size:.9rem; margin-bottom:28px;">עדכון אחרון: מאי 2026</p>

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
    <p>לשאלות בנושא תנאי השימוש: <a href="mailto:toppickp@gmail.com" style="color:#f59e0b;">toppickp@gmail.com</a></p>
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
