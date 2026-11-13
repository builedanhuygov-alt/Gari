import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Update Header.tsx
with open('_archive/legacy-react-frontend/src/components/Header.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = "    reports: { section: 'Analytics', title: 'Báo cáo & HTX' },"
replacement = """    reports: { section: 'Analytics', title: 'Báo cáo & HTX' },
    community: { section: 'Community', title: 'Cộng đồng & Tri thức' },"""

if target not in text:
    print("Error: target not found in Header.tsx")
    sys.exit(1)
text = text.replace(target, replacement, 1)

with open('_archive/legacy-react-frontend/src/components/Header.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

# 2. Update CommunityView.tsx
with open('_archive/legacy-react-frontend/src/components/CommunityView.tsx', 'r', encoding='utf-8') as f:
    cv = f.read()

cv_target = """  Flag,
  CheckCircle,
  Award,
  Filter,
  X,
  Share2"""

cv_replacement = """  CheckCircle,
  Award,
  X"""

cv = cv.replace(cv_target, cv_replacement, 1)
with open('_archive/legacy-react-frontend/src/components/CommunityView.tsx', 'w', encoding='utf-8') as f:
    f.write(cv)

print("Updated Header.tsx and CommunityView.tsx successfully!")
