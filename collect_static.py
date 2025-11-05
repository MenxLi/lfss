"""
Copy static files for distribution.
"""

import shutil
from pathlib import Path

this_dir = Path(__file__).parent
static_dir = this_dir / "lfss" / "svc" / "static"

doc_src = this_dir / "docs" / ".vitepress" / "dist"
doc_dst = static_dir / "docs"

front_src = this_dir / "frontend"
front_dst = static_dir / "panel"

if front_src.exists():
    if front_dst.exists():
        shutil.rmtree(front_dst)
    shutil.copytree(front_src, front_dst)
else:
    print("Warning: front-end files not found, skipping copying front-end files.")

if doc_src.exists():
    if doc_dst.exists():
        shutil.rmtree(doc_dst)
    shutil.copytree(doc_src, doc_dst)
else:
    print("Warning: documentation files not found, skipping copying documentation files.")
