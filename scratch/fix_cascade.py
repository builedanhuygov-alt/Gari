import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 1. In main definition around line 25586:
target1 = '''.content-body {
    flex: 1;
    padding: 24px 28px;
    max-width: 1440px;
    width: 100%;
    margin: 0 auto;
    min-width: 0;
    overflow-x: hidden;
    animation: pageFadeIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}'''

replacement1 = '''.content-body {
    flex: 1 0 auto;
    padding: 24px 28px;
    max-width: 1440px;
    width: 100%;
    margin: 0 auto;
    min-width: 0;
    animation: pageFadeIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}'''

if target1 not in css:
    print("Error: target1 not found")
    sys.exit(1)

css = css.replace(target1, replacement1, 1)

# 2. Add definitive desktop layout rule at the very end of style.css to guarantee winning cascade
desktop_override = '''

/* ==========================================================================
   GARI DESKTOP TWO-COLUMN STABLE LAYOUT & INDEPENDENT CONTENT SCROLL
   ========================================================================== */
@media (min-width: 1025px) {
    html:has(.app-shell),
    body:has(.app-shell) {
        height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
    }

    .app-shell {
        display: flex !important;
        height: 100vh !important;
        max-height: 100vh !important;
        width: 100vw !important;
        max-width: 100vw !important;
        overflow: hidden !important;
        position: relative !important;
    }

    .app-sidebar {
        flex: 0 0 var(--sidebar-width) !important;
        width: var(--sidebar-width) !important;
        min-width: var(--sidebar-width) !important;
        max-width: var(--sidebar-width) !important;
        height: 100vh !important;
        max-height: 100vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        overscroll-behavior: contain !important;
        position: relative !important;
        top: 0 !important;
        z-index: 40 !important;
    }

    .app-sidebar.collapsed {
        flex: 0 0 var(--sidebar-collapsed) !important;
        width: var(--sidebar-collapsed) !important;
        min-width: var(--sidebar-collapsed) !important;
        max-width: var(--sidebar-collapsed) !important;
    }

    .app-main {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        overscroll-behavior: contain !important;
        display: flex !important;
        flex-direction: column !important;
        position: relative !important;
    }

    .app-topbar {
        position: sticky !important;
        top: 0 !important;
        z-index: 30 !important;
        flex-shrink: 0 !important;
    }

    .content-body {
        flex: 1 0 auto !important;
        min-height: 0 !important;
        min-width: 0 !important;
        overflow: visible !important;
    }
}
'''

css = css + desktop_override

with open('frontend2/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Successfully updated CSS cascade priority for desktop independent scroll!")
