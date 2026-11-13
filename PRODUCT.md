# GARI 2.0 — Product Specification & Vision

**Product**: GARI AgriTech Platform (GARI AI Lab 2.0)  
**Mission**: Democratize deep-learning crop disease diagnosis and intelligent farm management for Vietnamese smallholders, agricultural cooperatives, and plant protection specialists.

---

## 1. Target User Personas & Jobs To Be Done (JTBD)

### 1.1 Persona A: Bác Hai — Nông Hộ Cá Thể (Smallholder Farmer)
- **Context**: 0.5 – 2.0 hectares in Lâm Đồng, Sơn La, or An Giang. Accesses platform primarily via smartphone in the field under harsh sunlight.
- **Job To Be Done**: *"When I spot yellowing or strange spots on my tomato/rice leaves, I want to take a fast, clear photo and immediately understand if it's blight or rust, so I know whether to spray biological neem oil or bring a leaf sample to the local commune station."*
- **Key Pain Point**: Confusing multi-step technical forms, slow cellular connectivity, and misleading AI confidence scores that pretend to be absolute medical truth.
- **GARI Solution**: 1-click mobile camera upload, immediate localized Vietnamese diagnosis with severity confidence ("Nghi ngờ cao", "Cần theo dõi", "Chưa chắc chắn"), ecological treatment guidelines without pushing commercial chemicals, and zero required setup.

### 1.2 Persona B: Chị Lan — Chủ Nhiệm Hợp Tác Xã (Cooperative Leader)
- **Context**: Manages 50–200 cooperative member farmers across 80 hectares of organic tea and vegetables.
- **Job To Be Done**: *"I want a single centralized dashboard where our members can submit leaf photos under our cooperative quota, so our cooperative technicians can monitor disease outbreaks early across all our plots."*
- **Key Pain Point**: Cross-user data leaks, test clutter in farm dropdowns, member accounts accidentally burning through organization quotas.
- **GARI Solution**: Multi-tenant cooperative spaces with strict RBAC (Owner, Admin, Member), centralized pool quotas (e.g. 1,000 checks/month), farm plot mapping, and clean isolated farm selectors.

### 1.3 Persona C: Kỹ Sư Đan Huỳnh — Chuyên Gia BVTV & Host Operator
- **Context**: Plant protection agronomist and platform host administrator responsible for AI model integrity, server uptime, and user moderation.
- **Job To Be Done**: *"I want an isolated Host Console where I can inspect model inference performance, monitor API abuse, and review user feedback/moderation cases before taking human-approved actions."*
- **Key Pain Point**: Operational data polluting user-facing agricultural dashboards, accidental permanent bans from automated AI filters.
- **GARI Solution**: Fully separated Host Server Admin Console (`/frontend2/host.html`), server telemetry, human-in-the-loop review queue where permanent bans require explicit operator confirmation.

---

## 2. Core Value Propositions

1. **44+ Local AI Disease Models**: Zero dependency on slow third-party overseas APIs; instant edge/local CPU inference tailored to Vietnamese crops.
2. **Nông Học Trách Nhiệm (Responsible Agronomy)**: Clear disclaimers stating that AI is a screening assistant, not a chemical prescription tool. Ecological and preventative first.
3. **Vietnamese Financial Infrastructure**: Frictionless QR payments via VietQR, SePay webhooks, and PayOS without credit card friction.
4. **Single Active Account Type Invariant**: Transparent account roles (`farmer`, `cooperative`, `expert`, `enterprise`) preventing permission ambiguity.
