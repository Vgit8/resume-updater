Resume Updater - Simple Automation (Option A)

This repo contains a simple automation that updates a Word resume (Viswanatha_Resume_Updated.docx) daily without any external login.

Files:
- auto_update_resume_simple.py : script that reads the resume, extracts keywords, writes a 3-line summary and keywords section.
- requirements.txt : python-docx dependency
- .github/workflows/resume-updater.yml : GitHub Actions workflow that runs 3 times daily (08:00, 15:00, 20:00 IST)
- Viswanatha_Resume_Updated.docx : your resume (place your real resume here)

Usage (local):
1. Put your Viswanatha_Resume_Updated.docx in the repo root.
2. python -m pip install -r requirements.txt
3. python auto_update_resume_simple.py

GitHub setup:
1. Create a private GitHub repository and push these files.
2. In GitHub, go to Actions → enable the workflow.
3. The workflow runs on schedule and updates the resume automatically.
