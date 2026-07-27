import type { Metadata, Viewport } from "next";
import "./globals.css";

const siteUrl = new URL(
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://hnldraft.com",
);
const siteName = "SHNL 36-0";
const title = "SHNL 36-0 — Povijesni HNL draft";
const description =
  "SHNL 36-0 je hrvatska HNL draft igra: zavrti povijesni klub i sezonu, sastavi momčad te odigraj sezonu solo ili uživo s prijateljima.";

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title,
  description,
  applicationName: siteName,
  category: "game",
  keywords: [
    "SHNL 36-0",
    "HNL draft",
    "HNL igra",
    "hrvatski nogomet",
    "povijesni HNL igrači",
    "nogometni draft",
  ],
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
  manifest: "/manifest.webmanifest",
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title,
    description,
    url: "/",
    siteName,
    locale: "hr_HR",
    type: "website",
    images: [{ url: "/og.png", width: 1731, height: 909, alt: title }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#101b19",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${siteUrl.href}#website`,
        url: siteUrl.href,
        name: siteName,
        alternateName: "HNL draft igra",
        description,
        inLanguage: "hr",
      },
      {
        "@type": "VideoGame",
        "@id": `${siteUrl.href}#game`,
        url: siteUrl.href,
        name: siteName,
        description,
        applicationCategory: "Game",
        genre: "Sports simulation game",
        gamePlatform: "Web browser",
        operatingSystem: "Any",
        inLanguage: "hr",
        isAccessibleForFree: true,
      },
    ],
  };

  return (
    <html lang="hr">
      <body>
        {children}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
          }}
        />
      </body>
    </html>
  );
}
