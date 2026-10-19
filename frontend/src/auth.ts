const DOMAIN = (import.meta.env.VITE_COGNITO_HOSTED_UI_URL as string | undefined)?.replace(/\/$/, "");
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined;
const REDIRECT_URI = (import.meta.env.VITE_COGNITO_REDIRECT_URI as string | undefined) || window.location.origin + "/";
const LOGOUT_URI = (import.meta.env.VITE_COGNITO_LOGOUT_URI as string | undefined) || window.location.origin + "/";

const VERIFIER_KEY = "techpulse.pkce_verifier";
const STATE_KEY = "techpulse.oauth_state";
const ACCESS_TOKEN_KEY = "techpulse.access_token";
const REFRESH_TOKEN_KEY = "techpulse.refresh_token";
const ID_TOKEN_KEY = "techpulse.id_token";
let refreshInFlight: Promise<string | undefined> | undefined;

function tokenExpiresSoon(token: string): boolean {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(atob(normalized)) as { exp?: number };
    return !claims.exp || claims.exp * 1000 <= Date.now() + 60_000;
  } catch {
    return true;
  }
}

async function refreshAccessToken(): Promise<string | undefined> {
  if (refreshInFlight) return refreshInFlight;
  const refreshToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
  if (!DOMAIN || !CLIENT_ID || !refreshToken) return undefined;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${DOMAIN}/oauth2/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "refresh_token",
          client_id: CLIENT_ID,
          refresh_token: refreshToken,
        }),
      });
      if (!response.ok) {
        sessionStorage.removeItem(ACCESS_TOKEN_KEY);
        sessionStorage.removeItem(ID_TOKEN_KEY);
        sessionStorage.removeItem(REFRESH_TOKEN_KEY);
        return undefined;
      }
      const tokens = (await response.json()) as { access_token?: string; id_token?: string; refresh_token?: string };
      if (!tokens.access_token) return undefined;
      sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
      if (tokens.id_token) sessionStorage.setItem(ID_TOKEN_KEY, tokens.id_token);
      return tokens.access_token;
    } catch {
      return undefined;
    } finally {
      refreshInFlight = undefined;
    }
  })();
  return refreshInFlight;
}

export function isRemoteApiConfigured(): boolean {
  return Boolean((import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim());
}

export function isAuthConfigured(): boolean {
  return Boolean(DOMAIN && CLIENT_ID);
}

function encodeBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function randomUrlSafe(length = 32): string {
  const bytes = new Uint8Array(length);
  window.crypto.getRandomValues(bytes);
  return encodeBase64Url(bytes);
}

async function createChallenge(verifier: string): Promise<string> {
  const digest = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return encodeBase64Url(new Uint8Array(digest));
}

export async function getAccessToken(): Promise<string | undefined> {
  const token = sessionStorage.getItem(ACCESS_TOKEN_KEY) ?? undefined;
  if (token && !tokenExpiresSoon(token)) return token;
  return refreshAccessToken();
}

export async function beginLogin(): Promise<void> {
  if (!DOMAIN || !CLIENT_ID) throw new Error("Cognito Hosted UI is not configured for this frontend.");
  const verifier = randomUrlSafe(48);
  const state = randomUrlSafe(24);
  const challenge = await createChallenge(verifier);
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  const query = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: "code",
    redirect_uri: REDIRECT_URI,
    scope: "openid email profile",
    code_challenge_method: "S256",
    code_challenge: challenge,
    state,
  });
  window.location.assign(`${DOMAIN}/oauth2/authorize?${query.toString()}`);
}

export async function finishLoginCallback(): Promise<boolean> {
  if (!DOMAIN || !CLIENT_ID) return false;
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  if (!code) return Boolean(await getAccessToken());

  const receivedState = url.searchParams.get("state");
  const expectedState = sessionStorage.getItem(STATE_KEY);
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);

  if (!receivedState || !expectedState || receivedState !== expectedState || !verifier) {
    throw new Error("Authentication state validation failed. Please sign in again.");
  }

  const response = await fetch(`${DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: CLIENT_ID,
      code,
      redirect_uri: REDIRECT_URI,
      code_verifier: verifier,
    }),
  });
  if (!response.ok) throw new Error("Could not exchange the sign-in code. Please try again.");
  const tokens = (await response.json()) as { access_token?: string; id_token?: string };
  if (!tokens.access_token) throw new Error("Identity provider did not return an access token.");
  sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  if (tokens.refresh_token) sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  if (tokens.id_token) sessionStorage.setItem(ID_TOKEN_KEY, tokens.id_token);
  url.searchParams.delete("code");
  url.searchParams.delete("state");
  url.searchParams.delete("session_state");
  window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
  return true;
}

export function signOut(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(ID_TOKEN_KEY);
  if (DOMAIN && CLIENT_ID) {
    const query = new URLSearchParams({ client_id: CLIENT_ID, logout_uri: LOGOUT_URI });
    window.location.assign(`${DOMAIN}/logout?${query.toString()}`);
  } else {
    window.location.assign("/");
  }
}
