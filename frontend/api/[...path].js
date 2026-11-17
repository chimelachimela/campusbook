export default async function handler(req, res) {
  const apiOrigin = process.env.CAMPUSBOOK_API_ORIGIN;
  const bypass = process.env.CAMPUSBOOK_API_VERCEL_BYPASS;

  if (!apiOrigin || !bypass) {
    res.status(500).json({ detail: "CampusBook preview API proxy is not configured." });
    return;
  }

  try {
    const pathParts = Array.isArray(req.query.path)
      ? req.query.path
      : req.query.path
        ? [req.query.path]
        : [];
    const target = new URL("/api/" + pathParts.map(encodeURIComponent).join("/"), apiOrigin);
    const incoming = new URL(req.url, "https://campusbook.local");
    incoming.searchParams.forEach((value, key) => target.searchParams.append(key, value));

    const headers = new Headers();
    for (const [key, rawValue] of Object.entries(req.headers || {})) {
      const lower = key.toLowerCase();
      if (["host", "connection", "content-length", "transfer-encoding", "x-forwarded-host", "x-forwarded-proto"].includes(lower)) continue;
      if (rawValue !== undefined) headers.set(key, Array.isArray(rawValue) ? rawValue.join(", ") : String(rawValue));
    }
    headers.set("x-vercel-protection-bypass", bypass);

    let body;
    if (!["GET", "HEAD"].includes((req.method || "GET").toUpperCase()) && req.body !== undefined) {
      body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
      if (!headers.has("content-type")) headers.set("content-type", "application/json");
    }

    const upstream = await fetch(target, {
      method: req.method || "GET",
      headers,
      body,
      redirect: "manual",
    });

    res.status(upstream.status);
    upstream.headers.forEach((value, key) => {
      if (!["connection", "content-length", "transfer-encoding", "set-cookie"].includes(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });
    const cookies = typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : upstream.headers.get("set-cookie");
    if (cookies && (Array.isArray(cookies) ? cookies.length : true)) res.setHeader("set-cookie", cookies);
    res.setHeader("cache-control", "no-store");
    res.send(Buffer.from(await upstream.arrayBuffer()));
  } catch (error) {
    res.status(502).json({ detail: "CampusBook could not reach its preview API." });
  }
}
