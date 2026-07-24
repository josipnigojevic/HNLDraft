#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { get } from "node:https";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const CLUBS = [
  ["419", "GNK Dinamo Zagreb"],
  ["447", "HNK Hajduk Split"],
  ["144", "HNK Rijeka"],
  ["327", "NK Osijek"],
  ["2362", "Slaven Belupo Koprivnica"],
  ["999", "NK Istra 1961"],
  ["11194", "NK Lokomotiva Zagreb"],
  ["599", "NK Varaždin"],
  ["5107", "NK Zagreb"],
  ["918", "NK Inter Zaprešić"],
  ["223", "HNK Šibenik"],
  ["2566", "NK Zadar"],
  ["420", "RNK Split"],
  ["314", "HNK Cibalia Vinkovci"],
  ["485", "NK Hrvatski Dragovoljac"],
  ["24575", "HNK Gorica"],
  ["11083", "NK Rudeš"],
  ["12109", "NK Lučko"],
  ["456", "HNK Vukovar 1991"],
];

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const outputDirectory = resolve(scriptDirectory, "../web/public/clubs");
const pngSignature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function download(url, redirectCount = 0) {
  return new Promise((resolveDownload, rejectDownload) => {
    const request = get(
      url,
      { headers: { "User-Agent": "36-0-HNL-local-asset-builder/1.0" } },
      (response) => {
        if (
          response.statusCode >= 300 &&
          response.statusCode < 400 &&
          response.headers.location &&
          redirectCount < 3
        ) {
          response.resume();
          resolveDownload(
            download(new URL(response.headers.location, url), redirectCount + 1),
          );
          return;
        }
        if (response.statusCode !== 200) {
          response.resume();
          rejectDownload(
            new Error(`Asset request returned HTTP ${response.statusCode}`),
          );
          return;
        }
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => resolveDownload(Buffer.concat(chunks)));
      },
    );
    request.on("error", rejectDownload);
  });
}

await mkdir(outputDirectory, { recursive: true });

const manifest = await Promise.all(
  CLUBS.map(async ([id, name]) => {
    const sourceUrl = `https://tmssl.akamaized.net/images/wappen/head/${id}.png`;
    const bytes = await download(sourceUrl);
    if (bytes.length < 1_000 || !bytes.subarray(0, 8).equals(pngSignature)) {
      throw new Error(`${name} (${id}) did not return a valid crest PNG`);
    }
    await writeFile(resolve(outputDirectory, `${id}.png`), bytes);
    return {
      id,
      name,
      file: `${id}.png`,
      sourceUrl,
      bytes: bytes.length,
    };
  }),
);

await writeFile(
  resolve(outputDirectory, "sources.json"),
  `${JSON.stringify(
    {
      generatedAt: new Date().toISOString(),
      usage:
        "Club crests are displayed for nominative identification. All marks remain the property of their respective owners.",
      crests: manifest,
    },
    null,
    2,
  )}\n`,
);

console.log(`Downloaded and validated ${manifest.length} club crests.`);
