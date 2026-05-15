import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "icon.icepanel.io",
        pathname: "/AWS/svg/**",
      },
    ],
  },
};

export default nextConfig;
