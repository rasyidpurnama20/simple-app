import { copyFile, mkdir } from "node:fs/promises";

await mkdir("static/vendor", { recursive: true });
await copyFile("node_modules/echarts/dist/echarts.min.js", "static/vendor/echarts.min.js");
await copyFile("node_modules/htmx.org/dist/htmx.min.js", "static/src/htmx.min.js");
