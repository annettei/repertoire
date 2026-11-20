// Forwards painting searches to the Art Institute of Chicago API from the server,
// identifying the app the way the museum asks (AIC-User-Agent header).
module.exports = async function handler(req, res) {
  try {
    const params = new URL(req.url, "http://x").searchParams;
    const p = params.get("p");
    params.delete("p");
    const url = "https://api.artic.edu/api/v1/artworks" + (p === "search" ? "/search" : "") + "?" + params.toString();
    const r = await fetch(url, {
      headers: {
        "AIC-User-Agent": "Repertoire personal portfolio project (annettei)",
        "User-Agent": "Repertoire/1.0 (personal portfolio project)",
        "Accept": "application/json"
      }
    });
    const body = await r.text();
    res.setHeader("Content-Type", r.headers.get("content-type") || "application/json");
    if (r.ok) res.setHeader("Cache-Control", "public, s-maxage=86400, stale-while-revalidate=604800");
    res.status(r.status).send(body);
  } catch (e) {
    res.status(502).json({ error: "upstream failed", detail: String(e && e.message || e) });
  }
};
