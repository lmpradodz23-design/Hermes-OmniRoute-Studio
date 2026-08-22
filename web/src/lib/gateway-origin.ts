/**
 * ORIGEM DO GATEWAY — para quando o cliente NÃO é servido pelo gateway.
 *
 * ── O problema que isto resolve ──────────────────────────────────────────────
 *
 * Hoje o `web/` é servido pelo próprio servidor Python, então `/api/status`
 * resolve contra a mesma origem e tudo funciona sem configuração. Isso vale
 * para o navegador do desktop e para a PWA instalada a partir do gateway.
 *
 * Não vale para o APK. Dentro do WebView do Capacitor o app é servido de
 * `https://localhost` a partir dos assets empacotados — `/api/status` ali
 * aponta para o próprio pacote, onde não existe gateway nenhum. O aparelho
 * precisa saber para onde falar.
 *
 * ── Por que isto é aditivo e não uma reescrita ───────────────────────────────
 *
 * Quando nada está configurado, `gatewayOrigin()` devolve string vazia e todas
 * as URLs continuam byte a byte iguais às de hoje. O caminho novo só existe
 * quando alguém o liga. Um módulo de rede compartilhado por 20 páginas não é
 * lugar para mudança de comportamento por default.
 *
 * ── O que a validação recusa, e por quê ──────────────────────────────────────
 *
 * `http:` só é aceito para destinos privados — loopback, faixas da RFC 1918,
 * link-local e nomes `.local` de mDNS. A regra é a mesma do
 * `network_security_config.xml` do APK, e de propósito: o caso real é o celular
 * falando com o PC de casa em `http://192.168.0.10:9119`, onde emitir
 * certificado válido para um IP privado não é algo que se peça a um usuário.
 * Um gateway na internet pública continua obrigado a HTTPS — quem quiser acesso
 * remoto usa um túnel, não uma porta aberta em texto claro.
 *
 * Recusa também: qualquer esquema fora de http/https (`javascript:`, `data:`,
 * `file:`), credenciais embutidas na URL (`https://user:senha@host` mandaria a
 * senha em todo request), e qualquer coisa com caminho, query ou fragmento —
 * isto é uma ORIGEM, e aceitar `https://host/qualquer/coisa` faria as chamadas
 * de API montarem URLs que ninguém previu.
 *
 * ── O que NÃO fica aqui ──────────────────────────────────────────────────────
 *
 * O token de sessão. A origem não é segredo — é o endereço de uma máquina na
 * rede do usuário — e `localStorage` serve bem para ela. O token é outra
 * história: no APK ele tem que ir para o Android Keystore, nunca para o
 * storage do WebView. Ver `audit/HERMES_MULTIPLATFORM.md` §4.
 */

const STORAGE_KEY = "hermes:gateway-origin";

/**
 * Destinos onde HTTP em texto claro é aceitável: a rede do próprio usuário.
 * Espelha `apps/mobile/android/app/src/main/res/xml/network_security_config.xml`
 * — se um dos dois mudar, o outro tem que mudar junto.
 */
export function isPrivateHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, "");

  if (host === "localhost" || host === "::1" || host.endsWith(".localhost")) {
    return true;
  }

  // mDNS: `meu-pc.local`
  if (host.endsWith(".local")) {
    return true;
  }

  const ipv4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);

  if (!ipv4) {
    // IPv6 unique-local (fc00::/7) e link-local (fe80::/10).
    return /^f[cd][0-9a-f]{2}:/.test(host) || /^fe[89ab][0-9a-f]:/.test(host);
  }

  const [a, b] = [Number(ipv4[1]), Number(ipv4[2])];

  if ([a, b, Number(ipv4[3]), Number(ipv4[4])].some((n) => n > 255)) {
    return false;
  }

  if (a === 127 || a === 10) return true; // loopback, 10.0.0.0/8
  if (a === 192 && b === 168) return true; // 192.168.0.0/16
  if (a === 172 && b >= 16 && b <= 31) return true; // 172.16.0.0/12
  if (a === 169 && b === 254) return true; // link-local
  if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT — Tailscale usa

  return false;
}

/**
 * Normaliza o que o usuário digitou. Devolve `null` quando o valor não pode ser
 * aceito — a mensagem de por quê é responsabilidade de quem chama, para que a
 * função continue pura e testável.
 */
export function normalizeGatewayOrigin(raw: string): null | string {
  const trimmed = (raw ?? "").trim();

  if (!trimmed) {
    return null;
  }

  // Sem esquema, assume-se `http` para host privado (o caso comum: alguém
  // digita `192.168.0.10:9119`) e `https` para o resto.
  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(trimmed);
  let candidate = trimmed;

  if (!hasScheme) {
    const hostOnly = trimmed.split("/")[0].split(":")[0];
    candidate = `${isPrivateHost(hostOnly) ? "http" : "https"}://${trimmed}`;
  }

  let url: URL;

  try {
    url = new URL(candidate);
  } catch {
    return null;
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return null;
  }

  // Credenciais na URL viajariam em todo request.
  if (url.username || url.password) {
    return null;
  }

  // Isto é uma ORIGEM. Caminho, query ou fragmento significam que o usuário
  // colou outra coisa — provavelmente uma página inteira do dashboard.
  if ((url.pathname && url.pathname !== "/") || url.search || url.hash) {
    return null;
  }

  if (!url.hostname) {
    return null;
  }

  // Texto claro só para a rede do próprio usuário.
  if (url.protocol === "http:" && !isPrivateHost(url.hostname)) {
    return null;
  }

  return url.origin;
}

function storage(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    // Safari em modo privado e WebViews com storage bloqueado lançam ao
    // simplesmente TOCAR em localStorage.
    return null;
  }
}

/**
 * A origem configurada, ou `""` quando o app é servido pelo próprio gateway —
 * que é o caso do navegador e da PWA, e onde nada muda.
 */
export function gatewayOrigin(): string {
  const store = storage();

  if (!store) {
    return "";
  }

  try {
    return normalizeGatewayOrigin(store.getItem(STORAGE_KEY) ?? "") ?? "";
  } catch {
    return "";
  }
}

/**
 * @returns a origem normalizada que foi gravada, ou `null` se o valor foi
 *          recusado — nesse caso nada é gravado.
 */
export function setGatewayOrigin(raw: string): null | string {
  const normalized = normalizeGatewayOrigin(raw);

  if (!normalized) {
    return null;
  }

  try {
    storage()?.setItem(STORAGE_KEY, normalized);
  } catch {
    // Sem storage o app ainda funciona nesta sessão; só não lembra depois.
  }

  return normalized;
}

export function clearGatewayOrigin(): void {
  try {
    storage()?.removeItem(STORAGE_KEY);
  } catch {
    // nada a fazer
  }
}

export const GATEWAY_ORIGIN_STORAGE_KEY = STORAGE_KEY;
