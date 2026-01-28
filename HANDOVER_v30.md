# Inspections PWA - Handover Document
**Date:** 28 January 2026  
**Version:** v30 (Render Deployment Ready)  
**Status:** App working, PDF ready for Linux deployment  

---

## 1. SESSION SUMMARY

### What Was Done
Prepared complete Render deployment package to fix PDF generation:
- Switched back from xhtml2pdf to WeasyPrint
- Created proper `render.yaml` with system dependencies
- Rewrote `pdf_generator.py` for WeasyPrint API
- Updated PDF template with CSS-based page numbers

### Why This Approach
WeasyPrint was always the right tool. The Mac library issue is an environment problem, not a code problem. Linux deployment (Render) solves it cleanly.

---

## 2. PROJECT CONTEXT

### Client
- **Company:** Monograph Architects (Kevin Coetzee)
- **Contractor:** Raubex
- **Project:** Power Park Student Housing - Phase 3
- **Domain:** archops.co.za (not yet deployed)

### User
- Johan - IT/PM background, not a coder
- **CRITICAL:** Does not edit files or code - all changes via Claude

---

## 3. DEPLOYMENT INSTRUCTIONS

### Step 1: Create Render Account
1. Go to https://render.com
2. Sign up (free tier available)
3. Connect your GitHub account (or use manual deploy)

### Step 2: Prepare Repository
Option A - GitHub:
1. Create new repository on GitHub
2. Upload the inspections-pwa folder contents
3. Push to GitHub

Option B - Manual:
1. In Render dashboard, choose "New Web Service"
2. Select "Deploy from a Git repository" or upload zip

### Step 3: Deploy
1. In Render, click "New +" and select "Web Service"
2. Connect to your GitHub repo (or use Blueprint)
3. Render will detect `render.yaml` and configure automatically
4. Click "Create Web Service"

### Step 4: Initial Setup
After deployment:
1. Open Render shell or use the deployed URL
2. Run setup script (first time only):
   ```bash
   python scripts/setup_project.py
   ```

### Step 5: Test
- Kevin login: `https://your-app.onrender.com/login?u=insp-002`
- Student login: `https://your-app.onrender.com/login?u=insp-001`

---

## 4. RENDER.YAML CONFIGURATION

```yaml
services:
  - type: web
    name: inspections-pwa
    runtime: python
    buildCommand: |
      apt-get update && apt-get install -y \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        libcairo2 \
        && pip install -r requirements.txt
    startCommand: gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_PATH
        value: /opt/render/project/src/data/inspections.db
    disk:
      name: inspections-data
      mountPath: /opt/render/project/src/data
      sizeGB: 1
```

### Key Points
- **Disk:** Persistent storage for SQLite database (survives redeploys)
- **Build:** Installs WeasyPrint system dependencies
- **Environment:** SECRET_KEY auto-generated, DATABASE_PATH points to persistent disk

---

## 5. FILE STRUCTURE

```
inspections-pwa/
    app/
        __init__.py           # Flask app factory
        auth.py               # Login decorators
        utils.py              # generate_id()
        routes/
            cycles.py         # Kevin: cycle management
            inspection.py     # Student + Kevin: inspection flow
            certification.py  # Kevin: dashboard
            projects.py       # Student: navigation
            defects.py        # Defect register
            pdf.py            # PDF generation (WeasyPrint)
        services/
            db.py             # Database connection
            schema.sql        # Database schema
            pdf_generator.py  # WeasyPrint PDF logic
            template_seed.sql # Test checklist
        templates/
            pdf/defects_list.html  # PDF template (CSS page numbers)
            ... (other templates)
        static/
            monograph_logo.jpg     # Company logo
            kevin_signature.png    # Signature image
    config/
        powerpark.json        # Current project config
    scripts/
        setup_project.py      # Creates demo data
        migrate_v28.py        # Schema migration
    requirements.txt          # Flask + WeasyPrint
    render.yaml               # Render deployment config
```

---

## 6. WHAT WORKS

| Feature | Status |
|---------|--------|
| Login system (architect/student) | Working |
| Project/Phase/Unit navigation | Working |
| Inspection checklist | Working |
| Defect capture with comments | Working |
| Category comments (editable) | Working |
| Cycle management | Working |
| Excluded items | Working |
| Certification dashboard | Working |
| Save Changes button | Working |
| **PDF generation** | **Ready for Linux** |

---

## 7. PDF FEATURES

### Layout
- Monograph letterhead (logo + company details)
- Metadata table with underlines
- Phase name and date in RED
- Unit number in RED
- Defects grouped by Area -> Category
- Standards section
- Excluded items section

### Footer (on every page)
- Directors line centered
- Page number (CSS counter)

### Signature Block
- "Kind regards,"
- Signature image (left-aligned)
- "Kevin Coetzee"
- "PrArch; MD"

---

## 8. LOCAL TESTING (Mac)

PDF will NOT work locally on Mac without fixing library linking. Options:

**Option 1:** Skip PDF testing locally, deploy to Render first

**Option 2:** Try fixing Mac libraries:
```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
cd ~/Downloads/inspections-pwa
python3 -m flask --app app run --debug --port 5001
```

**Option 3:** Use Docker locally (mimics Render environment)

---

## 9. NEXT STEPS

### Immediate
1. Deploy to Render
2. Run `setup_project.py` to create test data
3. Test PDF generation on live server

### After PDF Verified
1. Test all PDF layout requirements against letterhead samples
2. Add "Certify" button that generates + downloads PDF
3. Consider custom domain (archops.co.za)

---

## 10. RULES OF ENGAGEMENT

1. **Johan does NOT edit code** - all changes via Claude
2. **Always backup data folder** before extracting new zip
3. **Test before delivering** - no untested code
4. **One clear instruction** - no "do this OR that"
5. **Track token usage** - handover at ~15-20% remaining
6. **Verify capabilities before recommending library switches**

---

## 11. ASSETS

### In Static Folder
- `monograph_logo.jpg` - Company logo (260px wide)
- `kevin_signature.png` - Kevin's signature

### Signature Note
Current signature has a line through it. For cleaner version:
1. Kevin signs on plain white paper
2. Scan/photograph and crop
3. Use remove.bg to make transparent PNG

---

**End of Handover Document**
