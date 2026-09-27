# nestorowicz.nl

My homepage: two interactive figures, switchable as tabs, and a CV. Each page is a single self-contained HTML file with its data inside it: no dependencies, cookies, trackers or external requests. To preview, open `index.html` in a browser. Links between the pages point to folders (`cv/`, `../`), so the address bar shows `nestorowicz.nl/cv/` rather than `cv/index.html`; opened straight from disk they show the folder instead, so to click between the pages locally run `uv run python -m http.server` and open http://localhost:8000.

```text
nestorowicz.nl/                                                        licence
├── index.html                  the figures, Climate and Training      code AGPL, data CC BY, text ©
├── cv/index.html               the CV; prints on one A4 page          code AGPL, text ©
├── climate/
│   ├── triangle.py             every climate number and figure        AGPL-3.0-or-later
│   ├── triangle.png            static climate figure                  CC BY 4.0
│   └── DeBilt-TG-allversions.csv   KNMI source data, unchanged        CC BY 4.0, © KNMI
├── sport/
│   ├── sanitise_strava.py      Strava export to sessions.csv          AGPL-3.0-or-later
│   └── sessions.csv            published training data                CC BY 4.0
├── LICENSE                     AGPL-3.0 text, shown by GitHub
├── LICENSE-DATA                CC BY 4.0 text
└── README.md
```

One line of navigation on both pages, Climate, Training and CV, sticks to the top once you scroll, and each figure ends with a link to the other figure and to the CV. `index.html` is 207 KB, 71 KB compressed, of which 32 KB is the training data and 15 KB the portrait; `cv/index.html` is 14 KB compressed, most of it the portrait. Both scripts need only [uv](https://docs.astral.sh/uv/), which fetches Python and the dependencies on first run.

## The longer you look, the clearer it gets

![Every stretch of the De Bilt record as a triangle of tiles](climate/triangle.png)

Every stretch of ten years or more in the De Bilt temperature record, 1901–2025, is one tile above the years it spans: warm colours if it warmed, blue if it cooled. Short stretches go both ways, but no stretch of 46 years or more cooled, and the 46 years to 2025 warmed almost three times as fast as the 46 years to 1960.

```sh
cd climate
./triangle.py                       # prints every figure quoted on the page, writes triangle.png
./triangle.py --out triangle.svg    # any format matplotlib writes
./triangle.py --trends trends.csv   # every stretch, its trend and its 95% interval
./triangle.py --embed ../index.html # write the 125 annual means into the page
./triangle.py --fade                # fade stretches whose interval includes zero
```

```text
125 complete years, 1901–2025: 6,786 stretches of 10 years or more
10-year stretches: 72 warmed, 44 cooled
longest cooling stretch: 45 years, 1943–1987 at -0.0164 °C per decade
weakest 46-year stretch: 1934–1979 at +0.0040 °C per decade
whole record: +0.186 °C per decade
46 years to 1960: +0.153, 46 years to 2025: +0.439 °C per decade (2.9 times as fast)
lag-1 autocorrelation of the noise: 0.1296
10-year stretches clear of zero: 4 of 116; stretches under 20 years whose interval includes zero: 96%
```

**Method.** Daily mean temperature is taken from the `version2` column, averaged per complete calendar year and rounded to 0.01 °C. Each stretch gets an ordinary least-squares slope in °C per decade and a 95% interval. The interval uses the effective sample size of Santer et al. (2008), [doi:10.1002/joc.1756](https://doi.org/10.1002/joc.1756), because year-to-year noise is slightly persistent (lag-1 autocorrelation measured around a cubic fit). Colour runs from grey through yellow, orange and red for warming and through deepening blue for cooling, at full strength from 0.7 °C per decade. Computing the trend of every possible period is established; see Liebmann et al. (2010), [doi:10.1175/2010BAMS3030.1](https://doi.org/10.1175/2010BAMS3030.1), and Hannaford et al. (2013), [doi:10.5194/hess-17-2717-2013](https://doi.org/10.5194/hess-17-2717-2013). The page recomputes all of this in the browser from the embedded annual series and agrees with the script on every one of the 6,786 tiles, faded or not.

**Limits.** One station; the uncertainty of the homogenisation is not shown, and KNMI deliberately does not correct for gradual changes around the station such as urbanisation. Overlapping stretches share most of their years, so the tiles are not independent evidence and the fade is a guide rather than a formal test. The 46-year threshold is a knife edge: the longest cooling stretch cools by 0.016 °C per decade and the weakest 46-year stretch warms by 0.004. The figure shows how the temperature changed, not why.

**Data.** De Bilt only, from KNMI’s [homogenised daily temperature dataset for the five principal stations](https://dataplatform.knmi.nl/dataset/homogenization-daily-temperature-principal-stations-netherlands-1-0), version 2.0, described in de Valk and Brandsma (2026), KNMI report WR-26-01. It holds the raw series (`original`) and both homogenised versions from 1 January 1901. © KNMI, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## How my training branched out

One branch per sport, sprouting at my first session; each hair is a week, longer for more hours. Walking counts as cross-training. Below the branches, four small multiples track pace, speed, share of active days and sessions per active day by calendar year.

```sh
cd sport
./sanitise_strava.py path/to/activities.csv sessions.csv --embed ../index.html
```

`activities.csv` comes from Strava’s bulk export (on strava.com: Settings, My Account, Download or Delete Your Account, Request your archive). The script keeps four columns: the local date, the sport, moving time in minutes and, only for runs over 1 km and outdoor rides over 5 km, distance. Start times, titles, notes, gear, routes, heart rate and everything else never leave your computer, and `.gitignore` keeps the raw export out of the repository. Rides on a Wattbike or titled ‘indoor’ become indoor rides, sessions logged as generic training with ‘krachttraining’ or ‘strength’ in the title become strength, hikes become walks, and other sports (skating, badminton) are dropped. Pinned dependencies make the output byte-identical for the same export.

`--embed` writes the same bytes into the page, between `<script id="sessions" type="text/csv">` and `</script>`. The page computes every number and sentence from them, so they stay true when the data is rebuilt. Weeks run Monday to Sunday; all branches share one scale. A branch leaves the cycling stem at the date of the sport’s first session, and the lanes are ordered so that no branch crosses a lane that already exists. The small multiples use complete calendar years plus the current year so far, drawn hollow; pace and speed divide total moving time by total distance, and indoor rides are left out of speed because their speeds are simulated.

## Updating

- **Training data:** run the sanitiser with `--embed ../index.html` and commit `index.html` and `sport/sessions.csv`. Nothing else changes.
- **A new year of temperature data:** replace the KNMI file, change `last` in `annual()` and run `./triangle.py --embed ../index.html`. The sentences around the climate figure quote the script’s printout, so update them from it.
- **The CV:** edit `cv/index.html`. The header, bar and colours at the top of its stylesheet are shared with `index.html`; change both together.

## Publishing

The site is four files, uploaded to the web root with their folders: `index.html`, `cv/index.html`, `sport/sessions.csv` and `climate/triangle.png`. The CV then lives at `nestorowicz.nl/cv/`. Everything else stays in this repository. For example:

```sh
rsync -avR index.html cv/index.html sport/sessions.csv climate/triangle.png user@host:public_html/
```

The server should compress text (gzip or Brotli): `index.html` shrinks from 207 KB to 71 KB.

## Licences

- **Code**, meaning both scripts and the markup, styles and scripts of both pages, is free software under the [GNU Affero General Public License v3.0 or later](LICENSE). Anyone who runs a modified version for others, including as a website, must publish its source under the same licence.
- **Data and figures**, meaning `sessions.csv`, the training data embedded in `index.html` and `triangle.png`, are under [CC BY 4.0](LICENSE-DATA). Credit them as “Toni Nestorowicz, nestorowicz.nl”. The KNMI data stays under KNMI’s own CC BY 4.0 and needs its own credit: “© KNMI”.
- **Text**, meaning the CV and the sentences on the pages, is © Toni Nestorowicz, all rights reserved.

The scripts carry [SPDX](https://spdx.dev) headers and each page opens with a one-line notice, so every file states its licence where it is used.
