import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/components/Sidebar.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add Users to imports
target_import = "  SlidersHorizontal,\n  ChevronLeft,"
replacement_import = "  SlidersHorizontal,\n  Users,\n  ChevronLeft,"
if target_import not in text:
    print("Error: target_import not found")
    sys.exit(1)
text = text.replace(target_import, replacement_import, 1)

# 2. Add community navItem
target_item = """    {
      id: 'reports',
      label: 'Báo cáo & HTX',
      sublabel: 'Phân tích tổng hợp & CSV',
      icon: FileText,
    },"""

replacement_item = """    {
      id: 'reports',
      label: 'Báo cáo & HTX',
      sublabel: 'Phân tích tổng hợp & CSV',
      icon: FileText,
    },
    {
      id: 'community',
      label: 'Cộng đồng & Tri thức',
      sublabel: 'Diễn đàn & Cẩm nang BVTV',
      icon: Users,
    },"""

if target_item not in text:
    print("Error: target_item not found")
    sys.exit(1)
text = text.replace(target_item, replacement_item, 1)

with open('_archive/legacy-react-frontend/src/components/Sidebar.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated Sidebar.tsx with Community!")
