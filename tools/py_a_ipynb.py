"""Convierte notebooks/MOCIBA_proyecto.py (formato 'percent': celdas separadas por '# %%') a .ipynb."""
import sys
from pathlib import Path
import nbformat

src = Path(sys.argv[1]); dst = Path(sys.argv[2])
cells, cur, kind = [], [], None

def flush():
    if kind is None:
        return
    text = "\n".join(cur).strip("\n")
    if kind == "md":
        text = "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in text.splitlines())
        cells.append(nbformat.v4.new_markdown_cell(text))
    else:
        cells.append(nbformat.v4.new_code_cell(text))

for line in src.read_text(encoding="utf-8").splitlines():
    if line.startswith("# %%"):
        flush(); cur = []; kind = "md" if "[markdown]" in line else "code"
    else:
        cur.append(line)
flush()
nb = nbformat.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nb.metadata["language_info"] = {"name": "python"}
nbformat.write(nb, dst)
print(f"{len(cells)} celdas -> {dst}")
