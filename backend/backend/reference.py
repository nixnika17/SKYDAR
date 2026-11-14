# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Static reference data shared by the web app, the API and the Telegram bot."""

# SPHEREx has six H2RG detector arrays; each covers a part of 0.75-5.0 um (17 bands per array = 102 bands).
# Ranges are approximate and only used for labels / synthetic demo data.
DETECTORS = {
    "D1": dict(lo=0.75, hi=1.11), "D2": dict(lo=1.11, hi=1.64), "D3": dict(lo=1.64, hi=2.42),
    "D4": dict(lo=2.42, hi=3.82), "D5": dict(lo=3.82, hi=4.42), "D6": dict(lo=4.42, hi=5.00),
}

EPOCH_NOW = 2026.0  # epoch used to propagate catalogue positions (proper motion)

# Test targets named in the challenge. Positions are ICRS degrees.
# Fast movers are given for epoch ~2026.0 so they sit inside the field during the SPHEREx survey.
TARGETS = [
    dict(id="barnard", name="Barnard's Star", emoji="🏃", pm=10.3, vis="Needs a small telescope (magnitude ≈ 9.5).", ra=269.4463, dec=4.7679, fov=0.15,
         mission="Catch the runaway star",
         story="Barnard's Star is the fastest-moving star in our sky. It is only 6 light-years away, so it seems to race along: it crosses the width of the Moon about every 175 years.",
         look="Press ▶ and watch for one dot that slides while all the other stars stay put.",
         note="Fastest-moving star, ~10.3\"/yr. Position corrected to 2026.0."),
    dict(id="wise0855", name="WISE 0855-0714", emoji="❄️", pm=8.1, vis="Far too faint for backyard telescopes - only infrared space telescopes such as SPHEREx can see it.", ra=133.79513, dec=-7.24515, fov=0.15,
         mission="Hunt the iciest brown dwarf",
         story="A brown dwarf is a “failed star”: too small to shine like the Sun. WISE 0855 is only ~7 light-years away and about as cold as a winter day on Earth, so it is very faint, but it moves fast (~8 arcseconds a year).",
         look="Look near the centre for a faint dot that shifts between dates.",
         note="Coldest known brown dwarf, ~8\"/yr motion. Challenge position (older epoch): it has since moved ~2' west."),
    dict(id="epsindib", name="eps Indi Ba/Bb", emoji="🟤", pm=4.7, vis="The brown dwarfs are far too faint for amateurs, but their parent star Epsilon Indi A is naked-eye (magnitude 4.7) in the southern sky.", ra=331.0963, dec=-56.8003, fov=0.15,
         mission="Meet the twin brown dwarfs",
         story="Two brown dwarfs circle the star Epsilon Indi, just 12 light-years from us. They are tiny and dim, but they drift quickly across the sky.",
         look="Find the dot that slides against the background stars.",
         note="Brown-dwarf pair (unresolved) orbiting eps Indi A, ~4.7\"/yr. Approximate position for 2026.0."),
    dict(id="rdra", name="R Draconis", emoji="🔆", pm=0.0, vis="Binoculars when brightest (magnitude ≈ 6.7), a telescope when it is fainter.", ra=248.1788, dec=66.7559, fov=0.1,
         mission="Watch a star breathe",
         story="R Draconis is a giant star that swells and shrinks. Its brightness rises and falls over about 8 months.",
         look="Compare the dates: the star should look brighter on some and fainter on others.",
         note="Mira-type variable star."),
    dict(id="rwaur", name="RW Aurigae", emoji="💫", pm=0.0, vis="Small telescope (magnitude ≈ 10-13).", ra=76.9565, dec=30.4014, fov=0.1,
         mission="The flickering baby star",
         story="RW Aurigae is a very young star still wrapped in dust and gas. Clumps of dust drifting in front of it make it flicker unpredictably.",
         look="Check whether it gets brighter or dimmer from one date to the next.",
         note="Variable young star (T Tauri type)."),
]
