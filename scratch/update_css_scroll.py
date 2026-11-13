import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 1. Update .app-shell, .app-sidebar, and .app-main base & desktop styles
old_shell_block = '''.app-shell {
    display: flex;
    min-height: 100vh;
    background-color: var(--bg);
    width: 100%;
    max-width: 100vw;
    overflow-x: hidden;
}

/* --- SIDEBAR (Botanical Intelligence Forest Theme) --- */
.app-sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    max-width: var(--sidebar-width);
    flex-shrink: 0;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--sidebar-border);
    display: flex;
    flex-direction: column;
    position: sticky;
    top: 0;
    height: 100vh;
    z-index: 40;
    overflow-y: auto;
    overflow-x: hidden;
    transition: width var(--transition), transform var(--transition);
    color: var(--sidebar-text);
}'''

new_shell_block = '''.app-shell {
    display: flex;
    min-height: 100vh;
    background-color: var(--bg);
    width: 100%;
    max-width: 100vw;
}

/* --- SIDEBAR (Botanical Intelligence Forest Theme) --- */
.app-sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    max-width: var(--sidebar-width);
    flex-shrink: 0;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--sidebar-border);
    display: flex;
    flex-direction: column;
    height: 100vh;
    z-index: 40;
    overflow-y: auto;
    overflow-x: hidden;
    overscroll-behavior: contain;
    transition: width var(--transition), transform var(--transition);
    color: var(--sidebar-text);
}

/* Desktop Two-Column Application Layout with Independent Content Scroll */
@media (min-width: 1025px) {
    html:has(.app-shell),
    body:has(.app-shell) {
        height: 100vh;
        max-height: 100vh;
        overflow: hidden !important;
    }

    .app-shell {
        height: 100vh;
        max-height: 100vh;
        overflow: hidden;
        position: relative;
    }

    .app-sidebar {
        flex: 0 0 var(--sidebar-width);
        position: relative;
        top: 0;
        height: 100vh;
        max-height: 100vh;
    }

    .app-sidebar.collapsed {
        flex: 0 0 var(--sidebar-collapsed);
        width: var(--sidebar-collapsed);
        min-width: var(--sidebar-collapsed);
        max-width: var(--sidebar-collapsed);
    }

    .app-main {
        flex: 1;
        min-width: 0;
        height: 100vh;
        max-height: 100vh;
        overflow-y: auto;
        overflow-x: hidden;
        overscroll-behavior: contain;
        display: flex;
        flex-direction: column;
        position: relative;
    }

    .app-topbar {
        position: sticky;
        top: 0;
        z-index: 30;
        flex-shrink: 0;
    }

    .content-body {
        flex: 1;
        min-height: 0;
        min-width: 0;
    }
}'''

if old_shell_block not in css:
    print("Error: old_shell_block not found in style.css")
    sys.exit(1)

css = css.replace(old_shell_block, new_shell_block, 1)

with open('frontend2/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Successfully updated frontend2/style.css with desktop two-column independent scrolling!")
