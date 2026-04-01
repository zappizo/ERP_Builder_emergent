const textEncoder = new TextEncoder();

let crcTable;

function getCrcTable() {
  if (crcTable) {
    return crcTable;
  }

  crcTable = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let value = n;
    for (let bit = 0; bit < 8; bit += 1) {
      value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
    }
    crcTable[n] = value >>> 0;
  }

  return crcTable;
}

function crc32(bytes) {
  const table = getCrcTable();
  let crc = 0xffffffff;

  for (const byte of bytes) {
    crc = table[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }

  return (crc ^ 0xffffffff) >>> 0;
}

function writeUint16(view, offset, value) {
  view.setUint16(offset, value, true);
}

function writeUint32(view, offset, value) {
  view.setUint32(offset, value >>> 0, true);
}

function concatBytes(parts) {
  const totalLength = parts.reduce((sum, part) => sum + part.length, 0);
  const result = new Uint8Array(totalLength);
  let offset = 0;

  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }

  return result;
}

function createDosTimestamp(date = new Date()) {
  const year = Math.max(date.getFullYear(), 1980);
  const dosDate = ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
  const dosTime = (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
  return { dosDate, dosTime };
}

function normalizeZipPath(path) {
  return String(path || "untitled.txt").replace(/\\/g, "/").replace(/^\/+/, "");
}

function sanitizeFileName(name, fallback = "download") {
  const cleaned = String(name || "")
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1f]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return cleaned || fallback;
}

function buildZip(files, rootFolder = "") {
  const timestamp = createDosTimestamp();
  const entries = files.map((file, index) => {
    const relativePath = normalizeZipPath(file?.path || `file-${index + 1}.txt`);
    const zipPath = rootFolder ? normalizeZipPath(`${rootFolder}/${relativePath}`) : relativePath;
    const fileNameBytes = textEncoder.encode(zipPath);
    const contentBytes = textEncoder.encode(file?.content || "");

    return {
      fileNameBytes,
      contentBytes,
      crc: crc32(contentBytes),
      offset: 0,
      dosDate: timestamp.dosDate,
      dosTime: timestamp.dosTime,
    };
  });

  const localChunks = [];
  let offset = 0;

  for (const entry of entries) {
    entry.offset = offset;

    const localHeader = new Uint8Array(30 + entry.fileNameBytes.length);
    const localView = new DataView(localHeader.buffer);
    writeUint32(localView, 0, 0x04034b50);
    writeUint16(localView, 4, 20);
    writeUint16(localView, 6, 0x0800);
    writeUint16(localView, 8, 0);
    writeUint16(localView, 10, entry.dosTime);
    writeUint16(localView, 12, entry.dosDate);
    writeUint32(localView, 14, entry.crc);
    writeUint32(localView, 18, entry.contentBytes.length);
    writeUint32(localView, 22, entry.contentBytes.length);
    writeUint16(localView, 26, entry.fileNameBytes.length);
    writeUint16(localView, 28, 0);
    localHeader.set(entry.fileNameBytes, 30);

    localChunks.push(localHeader, entry.contentBytes);
    offset += localHeader.length + entry.contentBytes.length;
  }

  const centralChunks = [];
  const centralStart = offset;

  for (const entry of entries) {
    const centralHeader = new Uint8Array(46 + entry.fileNameBytes.length);
    const centralView = new DataView(centralHeader.buffer);
    writeUint32(centralView, 0, 0x02014b50);
    writeUint16(centralView, 4, 20);
    writeUint16(centralView, 6, 20);
    writeUint16(centralView, 8, 0x0800);
    writeUint16(centralView, 10, 0);
    writeUint16(centralView, 12, entry.dosTime);
    writeUint16(centralView, 14, entry.dosDate);
    writeUint32(centralView, 16, entry.crc);
    writeUint32(centralView, 20, entry.contentBytes.length);
    writeUint32(centralView, 24, entry.contentBytes.length);
    writeUint16(centralView, 28, entry.fileNameBytes.length);
    writeUint16(centralView, 30, 0);
    writeUint16(centralView, 32, 0);
    writeUint16(centralView, 34, 0);
    writeUint16(centralView, 36, 0);
    writeUint32(centralView, 38, 0);
    writeUint32(centralView, 42, entry.offset);
    centralHeader.set(entry.fileNameBytes, 46);

    centralChunks.push(centralHeader);
    offset += centralHeader.length;
  }

  const centralSize = offset - centralStart;
  const endRecord = new Uint8Array(22);
  const endView = new DataView(endRecord.buffer);
  writeUint32(endView, 0, 0x06054b50);
  writeUint16(endView, 4, 0);
  writeUint16(endView, 6, 0);
  writeUint16(endView, 8, entries.length);
  writeUint16(endView, 10, entries.length);
  writeUint32(endView, 12, centralSize);
  writeUint32(endView, 16, centralStart);
  writeUint16(endView, 20, 0);

  return concatBytes([...localChunks, ...centralChunks, endRecord]);
}

export function downloadFilesAsZip(files, options = {}) {
  if (!Array.isArray(files) || files.length === 0) {
    throw new Error("No files available to download.");
  }

  const archiveName = sanitizeFileName(options.archiveName, "generated-code");
  const rootFolder = sanitizeFileName(options.rootFolder || "", "");
  const zipBytes = buildZip(files, rootFolder);
  const blob = new Blob([zipBytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `${archiveName}.zip`;
  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadTextFile(content, options = {}) {
  const blob = new Blob([String(content ?? "")], {
    type: options.mimeType || "text/plain;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = options.fileName || "download.txt";
  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text) {
  const value = String(text ?? "");

  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to the textarea fallback.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  let copied = false;
  try {
    copied = document.execCommand("copy");
  } finally {
    textarea.remove();
  }

  return copied;
}
