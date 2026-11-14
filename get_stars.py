# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Download the full naked-eye star catalogue once:  python get_stars.py"""
from backend import stars
s = stars.get_catalog()
print(f"OK: {len(s)} stars (brightest {s[0]}, faintest {s[-1]})")
