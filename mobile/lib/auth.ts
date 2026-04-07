import * as AuthSession from "expo-auth-session";
import * as SecureStore from "expo-secure-store";
import * as WebBrowser from "expo-web-browser";

WebBrowser.maybeCompleteAuthSession();

const AUTH0_DOMAIN = process.env.EXPO_PUBLIC_AUTH0_DOMAIN ?? "YOUR_AUTH0_DOMAIN";
const AUTH0_CLIENT_ID =
  process.env.EXPO_PUBLIC_AUTH0_CLIENT_ID ?? "YOUR_AUTH0_CLIENT_ID";
const AUTH0_AUDIENCE =
  process.env.EXPO_PUBLIC_AUTH0_AUDIENCE ?? "https://api.zev.fitness";

const redirectUri = AuthSession.makeRedirectUri({ scheme: "zev" });

const discovery: AuthSession.DiscoveryDocument = {
  authorizationEndpoint: `https://${AUTH0_DOMAIN}/authorize`,
  tokenEndpoint: `https://${AUTH0_DOMAIN}/oauth/token`,
  revocationEndpoint: `https://${AUTH0_DOMAIN}/oauth/revoke`,
};

export async function login(): Promise<string | null> {
  const request = new AuthSession.AuthRequest({
    clientId: AUTH0_CLIENT_ID,
    redirectUri,
    scopes: ["openid", "profile", "email", "offline_access"],
    responseType: AuthSession.ResponseType.Code,
    extraParams: {
      audience: AUTH0_AUDIENCE,
    },
  });

  const result = await request.promptAsync(discovery);

  if (result.type === "success" && result.params.code) {
    const tokenResponse = await AuthSession.exchangeCodeAsync(
      {
        clientId: AUTH0_CLIENT_ID,
        code: result.params.code,
        redirectUri,
        extraParams: {
          code_verifier: request.codeVerifier ?? "",
        },
      },
      discovery
    );

    const accessToken = tokenResponse.accessToken;
    await SecureStore.setItemAsync("access_token", accessToken);

    if (tokenResponse.refreshToken) {
      await SecureStore.setItemAsync(
        "refresh_token",
        tokenResponse.refreshToken
      );
    }

    return accessToken;
  }

  return null;
}

export async function logout(): Promise<void> {
  await SecureStore.deleteItemAsync("access_token");
  await SecureStore.deleteItemAsync("refresh_token");

  await WebBrowser.openAuthSessionAsync(
    `https://${AUTH0_DOMAIN}/v2/logout?client_id=${AUTH0_CLIENT_ID}&returnTo=${redirectUri}`,
    redirectUri
  );
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync("access_token");
}
