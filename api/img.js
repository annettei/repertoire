// Fetches a painting image from the Art Institute of Chicago's image server on the
// server side and passes it through, so visitors' browsers don't need to reach the museum directly.
module.exports = async function handler(req, res) {
  try {
    const id = new URL(req.url, "http://x").searchParams.get("id") || "";
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
      res.status(400).send("bad id");
      return;
    }
    const r = await fetch("https://www.artic.edu/iiif/2/" + id + "/full/843,/0/default.jpg", {
      headers: {
        "AIC-User-Agent": "Repertoire personal portfolio project (annettei)",
        "User-Agent": "Repertoire/1.0 (personal portfolio project)",
        "Accept": "image/jpeg,image/*"
      }
    });
    if (!r.ok) { res.status(r.status).send("upstream " + r.status); return; }
    const buf = Buffer.from(await r.arrayBuffer());
    res.setHeader("Content-Type", r.headers.get("content-type") || "image/jpeg");
    res.setHeader("Cache-Control", "public, s-maxage=2592000, max-age=86400, stale-while-revalidate=604800");
    res.status(200).send(buf);
  } catch (e) {
    res.status(502).send("upstream failed");
  }
};
