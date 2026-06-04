/**
 * LegalShield AI — Cloudflare Edge Gateway
 *
 * Responsabilidades:
 *  1. Rate limit por IP via KV (janela deslizante)
 *  2. Cache de respostas de polling de análise (GET /api/v1/analysis/:id) por 2s
 *  3. Proxy transparente para o backend Render (streaming preservado)
 *  4. Injeção de security headers em toda resposta
 */

export interface Env {
  // KV namespace — gerado por: wrangler types (nunca escrever à mão)
  RATE_LIMIT_KV: KVNamespace;

  // Variáveis não-sensíveis (definidas em wrangler.jsonc -> vars)
  RATE_LIMIT_WINDOW_MS: string;
  RATE_LIMIT_MAX_REQUESTS: string;
  ANALYSIS_CACHE_TTL_SECONDS: string;

  // Segredo: npx wrangler secret put RENDER_BACKEND_URL
  RENDER_BACKEND_URL: string;
}

// ---------------------------------------------------------------------------
// Ponto de entrada
// ---------------------------------------------------------------------------

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // 1. Rate limit — bloquear IPs abusivos antes de tocar o Render
    const rateLimitResponse = await checkRateLimit(request, env, ctx);
    if (rateLimitResponse) return rateLimitResponse;

    // 2. Cache de polling — responder da edge sem bater no Render
    const cachedResponse = await tryCacheGet(request);
    if (cachedResponse) {
      return addSecurityHeaders(new Response(cachedResponse.body, cachedResponse), "HIT");
    }

    // 3. Proxy para Render (streaming preservado — nunca await response.text())
    const upstreamRequest = buildUpstreamRequest(request, env);
    const upstreamResponse = await fetch(upstreamRequest);

    // 4. Cachear respostas de polling intermediárias em background
    ctx.waitUntil(maybeCachePut(request, upstreamResponse.clone(), env));

    return addSecurityHeaders(upstreamResponse, "MISS");
  },
} satisfies ExportedHandler<Env>;

// ---------------------------------------------------------------------------
// Rate Limiting — janela deslizante via KV
// ---------------------------------------------------------------------------

async function checkRateLimit(
  request: Request,
  env: Env,
  ctx: ExecutionContext
): Promise<Response | null> {
  const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
  const windowMs = parseInt(env.RATE_LIMIT_WINDOW_MS, 10);
  const maxRequests = parseInt(env.RATE_LIMIT_MAX_REQUESTS, 10);
  const now = Date.now();
  const windowStart = now - windowMs;
  const kvKey = `rl:${ip}`;

  // Ler timestamps das requisições anteriores nesta janela
  const raw = await env.RATE_LIMIT_KV.get(kvKey);
  const timestamps: number[] = raw ? (JSON.parse(raw) as number[]) : [];

  // Filtrar apenas os timestamps dentro da janela atual
  const recent = timestamps.filter((t) => t > windowStart);

  if (recent.length >= maxRequests) {
    const retryAfterMs = windowMs - (now - recent[0]);
    return new Response(
      JSON.stringify({ error: "Too Many Requests", retry_after_ms: retryAfterMs }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(Math.ceil(retryAfterMs / 1000)),
          "X-RateLimit-Limit": String(maxRequests),
          "X-RateLimit-Remaining": "0",
        },
      }
    );
  }

  // Persistir atualização em background (não bloqueia a resposta)
  ctx.waitUntil(
    env.RATE_LIMIT_KV.put(kvKey, JSON.stringify([...recent, now]), {
      expirationTtl: Math.ceil(windowMs / 1000) + 1,
    })
  );

  return null;
}

// ---------------------------------------------------------------------------
// Cache de polling de análise
// ---------------------------------------------------------------------------

const ANALYSIS_POLLING_PATTERN = /^\/api\/v1\/analysis\/[^/]+$/;

function isAnalysisPollingRequest(request: Request): boolean {
  if (request.method !== "GET") return false;
  const { pathname } = new URL(request.url);
  return ANALYSIS_POLLING_PATTERN.test(pathname);
}

async function tryCacheGet(request: Request): Promise<Response | null> {
  if (!isAnalysisPollingRequest(request)) return null;

  const cache = caches.default;
  const cached = await cache.match(request);
  return cached ?? null;
}

async function maybeCachePut(
  request: Request,
  response: Response,
  env: Env
): Promise<void> {
  if (!isAnalysisPollingRequest(request)) return;
  if (!response.ok) return;

  // Ler o body para verificar se a análise ainda está em progresso
  // (clonar antes — o original já foi enviado ao cliente)
  let body: Record<string, unknown>;
  try {
    body = (await response.clone().json()) as Record<string, unknown>;
  } catch {
    return;
  }

  const status = body["status"];
  // Só cachear estados intermediários — "completed" e "failed" mudam a UX
  if (status === "completed" || status === "failed") return;

  const ttl = parseInt(env.ANALYSIS_CACHE_TTL_SECONDS, 10);
  const cacheableResponse = new Response(response.body, {
    status: response.status,
    headers: {
      ...Object.fromEntries(response.headers),
      "Cache-Control": `public, max-age=${ttl}, s-maxage=${ttl}`,
    },
  });

  await caches.default.put(request, cacheableResponse);
}

// ---------------------------------------------------------------------------
// Proxy para Render
// ---------------------------------------------------------------------------

function buildUpstreamRequest(request: Request, env: Env): Request {
  const url = new URL(request.url);
  const backendUrl = new URL(env.RENDER_BACKEND_URL);

  url.protocol = backendUrl.protocol;
  url.hostname = backendUrl.hostname;
  url.port = backendUrl.port;

  // Preservar todos os headers originais + identificar a origem
  const headers = new Headers(request.headers);
  headers.set("X-Forwarded-Host", request.headers.get("host") ?? "");
  headers.set("X-Gateway", "legalshield-edge");

  return new Request(url.toString(), {
    method: request.method,
    headers,
    body: request.body,
    // Preservar streaming — nunca consumir o body aqui
    duplex: "half",
  } as RequestInit);
}

// ---------------------------------------------------------------------------
// Security headers
// ---------------------------------------------------------------------------

const SECURITY_HEADERS: Record<string, string> = {
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'", // frontend usa JS inline no Jinja
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
  ].join("; "),
};

function addSecurityHeaders(response: Response, cacheStatus?: "HIT" | "MISS"): Response {
  const newHeaders = new Headers(response.headers);

  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    newHeaders.set(key, value);
  }

  if (cacheStatus) {
    newHeaders.set("X-Cache", cacheStatus);
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}
