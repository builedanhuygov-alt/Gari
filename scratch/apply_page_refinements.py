import re

# 1. Update farms.html
with open('frontend2/farms.html', 'r', encoding='utf-8') as f:
    farms_html = f.read()

farms_html = farms_html.replace(
    'class="kpi-row botanical-kpis" style="grid-template-columns: repeat(3, 1fr); margin-bottom:20px;"',
    'class="kpi-row botanical-kpis kpi-row-3" style="margin-bottom:20px;"'
)

with open('frontend2/farms.html', 'w', encoding='utf-8') as f:
    f.write(farms_html)
print("Updated farms.html")

# 2. Update disease.html
with open('frontend2/disease.html', 'r', encoding='utf-8') as f:
    disease_html = f.read()

disease_html = disease_html.replace(
    'style="display:grid; grid-template-columns: 1.5fr 1fr auto; gap:12px; align-items:center;"',
    'class="disease-filter-grid"'
)

with open('frontend2/disease.html', 'w', encoding='utf-8') as f:
    f.write(disease_html)
print("Updated disease.html")

# 3. Update support.html
with open('frontend2/support.html', 'r', encoding='utf-8') as f:
    support_html = f.read()

support_html = support_html.replace(
    'style="display:grid; grid-template-columns: 1.5fr 1fr; gap:20px; align-items:start;"',
    'class="support-layout-grid"'
)

with open('frontend2/support.html', 'w', encoding='utf-8') as f:
    f.write(support_html)
print("Updated support.html")

# 4. Append responsive rules to style.css
css_rules = """

/* ==========================================================================
   Product-wide Responsive Grid & Accessibility Helpers
   ========================================================================== */

.kpi-row-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

@media (max-width: 900px) {
    .kpi-row-3 {
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
    }
}

@media (max-width: 600px) {
    .kpi-row-3 {
        grid-template-columns: 1fr;
        gap: 10px;
    }
}

.disease-filter-grid {
    display: grid;
    grid-template-columns: 1.5fr 1fr auto;
    gap: 12px;
    align-items: center;
}

@media (max-width: 768px) {
    .disease-filter-grid {
        grid-template-columns: 1fr;
        gap: 10px;
    }
}

.support-layout-grid {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 20px;
    align-items: start;
}

@media (max-width: 900px) {
    .support-layout-grid {
        grid-template-columns: 1fr;
        gap: 16px;
    }
}

/* Accessibility & Focus Indicators */
:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
}

button:focus-visible,
a:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
}

/* Modal Viewport Bounds */
.modal-dialog {
    max-height: 90vh;
    overflow-y: auto;
}

/* Reduced Motion Respect */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}
"""

with open('frontend2/style.css', 'a', encoding='utf-8') as f:
    f.write(css_rules)
print("Updated style.css with responsive & a11y rules")
