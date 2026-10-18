import { type DeliveryFileType } from "./api";

const extensions: Record<
  Exclude<DeliveryFileType, "all" | "other">,
  string[]
> = {
  document: [
    "pdf",
    "doc",
    "docx",
    "odt",
    "rtf",
    "md",
    "mdx",
    "txt",
    "rst",
    "tex",
  ],
  spreadsheet: ["csv", "tsv", "xls", "xlsx", "ods"],
  presentation: ["ppt", "pptx", "odp"],
  image: [
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg",
    "avif",
    "bmp",
    "tif",
    "tiff",
    "ico",
  ],
  code: [
    "html",
    "htm",
    "js",
    "jsx",
    "ts",
    "tsx",
    "json",
    "py",
    "ipynb",
    "sh",
    "bash",
    "ps1",
    "css",
    "scss",
    "sql",
    "xml",
    "yaml",
    "yml",
    "toml",
    "ini",
    "rs",
    "go",
    "java",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "rb",
    "php",
    "swift",
    "kt",
  ],
};

// Presentation only: matching and pagination belong to the Gateway.
export function deliveryFileType(
  path: string,
): Exclude<DeliveryFileType, "all"> {
  const filename = path.split("/").at(-1) ?? path;
  const dot = filename.lastIndexOf(".");
  const extension = dot > 0 ? filename.slice(dot + 1).toLowerCase() : "";
  for (const [category, suffixes] of Object.entries(extensions)) {
    if (suffixes.includes(extension)) {
      return category as Exclude<DeliveryFileType, "all" | "other">;
    }
  }
  return "other";
}
