"""
Generates docs/index.html — a shareable static product page for GitHub Pages.
Run: python export_page.py
"""

import json
from pathlib import Path
from src.db import init_db, get_all

DOCS = Path(__file__).parent / "docs"
DOCS.mkdir(exist_ok=True)

def build():
    init_db()
    products = [p for p in get_all() if p["status"] == "ready_for_video"]

    rows_data = []
    for p in products:
        rows_data.append({
            "name":         p.get("name") or p["asin"],
            "category":     p.get("category") or "—",
            "rating":       round(p.get("rating") or 0, 1),
            "price":        round(p.get("price_usd") or 0, 2),
            "reviews":      p.get("review_count") or 0,
            "ships_israel": bool(p.get("ships_to_israel")),
            "link":         p.get("affiliate_link") or f"https://www.amazon.com/dp/{p['asin']}/",
        })

    categories = sorted({r["category"] for r in rows_data if r["category"] and r["category"] != "—"})
    max_price   = max((r["price"] for r in rows_data if r["price"]), default=500)
    products_json = json.dumps(rows_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Winning Products — Affiliation</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css">
  <style>
    body {{ background: #f0f2f5; font-family: 'Segoe UI', sans-serif; }}
    .hero {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 48px 24px 32px; text-align: center; }}
    .hero h1 {{ font-weight: 800; font-size: 2rem; letter-spacing: -0.5px; }}
    .hero p {{ color: #adb5bd; margin-bottom: 0; }}
    .badge-rating {{ background: #fff3cd; color: #856404; font-weight: 600; }}
    .badge-ship {{ background: #d1e7dd; color: #0a3622; }}
    .card {{ border: none; border-radius: 14px; box-shadow: 0 1px 6px rgba(0,0,0,.08); }}
    .link-btn {{ font-size: .8rem; }}
    .product-name {{ max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-block; }}
    .stat {{ text-align: center; }}
    .stat-num {{ font-size: 1.8rem; font-weight: 700; }}
    footer {{ color: #adb5bd; font-size: .8rem; text-align: center; padding: 32px 0; }}
    .filter-bar {{ background: #fff; border-radius: 14px; padding: 20px 24px; box-shadow: 0 1px 6px rgba(0,0,0,.08); margin-bottom: 20px; }}
    .filter-bar label {{ font-size: .78rem; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: .5px; }}
    #results-count {{ font-size: .85rem; color: #888; }}
  </style>
</head>
<body>

<div class="hero">
  <h1>🔗 Winning Products</h1>
  <p id="hero-sub">{len(products)} products · Ship to Israel 🇮🇱</p>
</div>

<div class="container py-4">

  <!-- Stats -->
  <div class="row g-3 mb-4 justify-content-center">
    <div class="col-6 col-sm-3 stat">
      <div class="card p-3">
        <div class="text-muted small">Products</div>
        <div class="stat-num text-primary" id="stat-count">{len(products)}</div>
      </div>
    </div>
    <div class="col-6 col-sm-3 stat">
      <div class="card p-3">
        <div class="text-muted small">Avg Rating</div>
        <div class="stat-num text-warning">
          {round(sum(p["rating"] for p in rows_data if p["rating"]) / max(len([p for p in rows_data if p["rating"]]), 1), 1)} ★
        </div>
      </div>
    </div>
    <div class="col-6 col-sm-3 stat">
      <div class="card p-3">
        <div class="text-muted small">Sources</div>
        <div class="stat-num text-success">{len(categories)}</div>
      </div>
    </div>
    <div class="col-6 col-sm-3 stat">
      <div class="card p-3">
        <div class="text-muted small">Ships to</div>
        <div class="stat-num">🇮🇱</div>
      </div>
    </div>
  </div>

  <!-- Filters -->
  <div class="filter-bar">
    <div class="row g-3 align-items-end">
      <div class="col-12 col-sm-6 col-md-3">
        <label class="form-label mb-1">Category</label>
        <select class="form-select form-select-sm" id="f-category">
          <option value="">All categories</option>
          {"".join(f'<option value="{c}">{c.title()}</option>' for c in categories)}
        </select>
      </div>
      <div class="col-6 col-sm-3 col-md-2">
        <label class="form-label mb-1">Min Price ($)</label>
        <input type="number" class="form-control form-control-sm" id="f-min-price" placeholder="0" min="0">
      </div>
      <div class="col-6 col-sm-3 col-md-2">
        <label class="form-label mb-1">Max Price ($)</label>
        <input type="number" class="form-control form-control-sm" id="f-max-price" placeholder="Any" min="0">
      </div>
      <div class="col-6 col-sm-3 col-md-2">
        <label class="form-label mb-1">Min Rating (★)</label>
        <input type="number" class="form-control form-control-sm" id="f-rating" placeholder="0" min="0" max="5" step="0.1">
      </div>
      <div class="col-6 col-sm-3 col-md-2">
        <label class="form-label mb-1">Search</label>
        <input type="text" class="form-control form-control-sm" id="f-search" placeholder="Product name...">
      </div>
      <div class="col-12 col-md-2 d-flex gap-2">
        <button class="btn btn-sm btn-primary w-100" onclick="applyFilters()">Filter</button>
        <button class="btn btn-sm btn-outline-secondary w-100" onclick="clearFilters()">Clear</button>
      </div>
    </div>
    <div class="mt-2" id="results-count"></div>
  </div>

  <!-- Table -->
  <div class="card p-3 p-md-4">
    <div class="table-responsive">
      <table id="products-table" class="table table-hover table-sm w-100">
        <thead class="table-dark">
          <tr>
            <th>#</th>
            <th>Product</th>
            <th>Category</th>
            <th>Rating</th>
            <th>Price</th>
            <th>Reviews</th>
            <th>Link</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<footer>Generated by Affiliation Pipeline · Products sourced from Amazon</footer>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
const allProducts = {products_json};
let dt;

function renderTable(data) {{
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  data.forEach((p, i) => {{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-muted small">${{i+1}}</td>
      <td><span class="product-name" title="${{p.name}}">${{p.name}}</span></td>
      <td><span class="badge bg-secondary">${{p.category}}</span></td>
      <td><span class="badge badge-rating">${{p.rating > 0 ? p.rating.toFixed(1) + ' ★' : '—'}}</span></td>
      <td class="fw-semibold">$${{p.price.toFixed(2)}}</td>
      <td class="text-muted small">${{p.reviews > 0 ? p.reviews.toLocaleString() : '—'}}</td>
      <td><a href="${{p.link}}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-primary link-btn">Open ↗</a></td>
    `;
    tbody.appendChild(tr);
  }});

  if (dt) {{ dt.destroy(); }}
  dt = $('#products-table').DataTable({{
    pageLength: 25,
    order: [[4, 'asc']],
    columnDefs: [{{ orderable: false, targets: 6 }}],
    searching: false,
    info: false,
  }});

  document.getElementById('results-count').textContent =
    data.length === allProducts.length
      ? `Showing all ${{data.length}} products`
      : `Showing ${{data.length}} of ${{allProducts.length}} products`;
}}

function clearFilters() {{
  document.getElementById('f-category').value = '';
  document.getElementById('f-min-price').value = '';
  document.getElementById('f-max-price').value = '';
  document.getElementById('f-rating').value = '';
  document.getElementById('f-search').value = '';
  renderTable(allProducts);
}}

function applyFilters() {{
  const cat      = document.getElementById('f-category').value.toLowerCase();
  const minPrice = parseFloat(document.getElementById('f-min-price').value) || 0;
  const maxPrice = parseFloat(document.getElementById('f-max-price').value) || Infinity;
  const minRating= parseFloat(document.getElementById('f-rating').value) || 0;
  const search   = document.getElementById('f-search').value.toLowerCase();

  const filtered = allProducts.filter(p => {{
    if (cat && p.category.toLowerCase() !== cat) return false;
    if (p.price < minPrice || p.price > maxPrice) return false;
    if (minRating > 0 && p.rating < minRating) return false;
    if (search && !p.name.toLowerCase().includes(search)) return false;
    return true;
  }});

  renderTable(filtered);
}}

// Allow Enter key on filter inputs
document.addEventListener('DOMContentLoaded', () => {{
  ['f-min-price','f-max-price','f-rating','f-search'].forEach(id => {{
    document.getElementById(id).addEventListener('keydown', e => {{
      if (e.key === 'Enter') applyFilters();
    }});
  }});
  document.getElementById('f-category').addEventListener('change', applyFilters);
  renderTable(allProducts);
}});
</script>
</body>
</html>"""

    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Generated docs/index.html with {len(products)} products.")

if __name__ == "__main__":
    build()
