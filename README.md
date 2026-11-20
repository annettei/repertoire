# Repertoire

A web app that helps pianists choose what to play next. Enter a piece you're learning, pick a genre, and get five recommendations: one a step easier, three at your level, and one reach. Each comes with a 30-second preview, a public-domain painting, and a fun fact.

## Features

- Search a catalog of 212 pieces by 27 composers across 8 genres (or pick a level if your piece isn't listed)
- Difficulty-aware mix of recommendations, with composer variety
- 30-second previews from the Apple Music (iTunes) Search API, with a credit link; no audio is stored
- Public-domain paintings from the Art Institute of Chicago, matched to each composer's homeland and era
- Fun facts for every piece and painting
- Forgiving search (for example, "Toccatina by Kapustin"), automatic recovery when a recording won't load, and a mobile layout

## Files

- `index.html`: the whole app (HTML, CSS and JavaScript)
- `picks.js`: the chosen Apple Music recording for each piece
- `resolve_previews.py`: script that finds and scores the best recording for each piece and writes `picks.js` and `review.csv`

## Run it

The app must be served from a web address (not opened as a local file) for previews and paintings to load. For a quick local test:

```
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Notes

Difficulty levels, composition years, and piece facts were written by hand and have not yet been reviewed by a teacher. Previews are provided by Apple Music and paintings by the Art Institute of Chicago under their own terms.
