import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SHNL 36-0",
    short_name: "SHNL 36-0",
    description:
      "Povijesna HNL draft igra za solo i live sobe s prijateljima.",
    start_url: "/",
    display: "standalone",
    background_color: "#f1efe5",
    theme_color: "#101b19",
    lang: "hr",
    icons: [
      {
        src: "/favicon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
