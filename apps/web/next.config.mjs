import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    serverActions: { bodySizeLimit: "50mb" },
  },
  // No `/api/:path*` rewrite — that would bypass the auth-aware proxy at
  // src/app/api/v1/[...path]/route.ts which reads the http-only access cookie
  // and attaches the bearer token. The proxy itself talks to API_BASE_URL.
};

export default withNextIntl(nextConfig);
