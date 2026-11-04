import { createCipheriv, createDecipheriv, randomBytes } from "crypto";

const ALGO = "aes-256-gcm" as const;
const BASE64_PATTERN =
  /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;

function decodeBase64(value: string, errorMessage: string): Buffer {
  if (!BASE64_PATTERN.test(value)) throw new Error(errorMessage);
  const decoded = Buffer.from(value, "base64");
  if (decoded.toString("base64") !== value) throw new Error(errorMessage);
  return decoded;
}

function getKey(): Buffer {
  const b64 = process.env.CREDENTIAL_ENCRYPTION_KEY?.trim();
  if (!b64) throw new Error("CREDENTIAL_ENCRYPTION_KEY is not set");
  const key = decodeBase64(b64, "CREDENTIAL_ENCRYPTION_KEY must be valid base64");
  if (key.length !== 32)
    throw new Error("CREDENTIAL_ENCRYPTION_KEY must decode to exactly 32 bytes");
  return key;
}

/**
 * Encrypt a plaintext string with AES-256-GCM.
 * Returns "ivB64:tagB64:ciphertextB64" — all base64, colon-delimited.
 */
export function encrypt(plaintext: string): string {
  const key = getKey();
  const iv = randomBytes(12); // 96-bit IV — GCM standard
  const cipher = createCipheriv(ALGO, key, iv);
  const encrypted = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();
  return [iv.toString("base64"), tag.toString("base64"), encrypted.toString("base64")].join(":");
}

/**
 * Decrypt a value produced by encrypt().
 * Throws if the key is wrong or the ciphertext is tampered.
 */
export function decrypt(ciphertext: string): string {
  const key = getKey();
  const parts = ciphertext.split(":");
  if (parts.length !== 3) throw new Error("Invalid ciphertext format");
  const [ivB64, tagB64, dataB64] = parts;
  const iv = decodeBase64(ivB64, "Invalid ciphertext encoding");
  const tag = decodeBase64(tagB64, "Invalid ciphertext encoding");
  const data = decodeBase64(dataB64, "Invalid ciphertext encoding");
  if (iv.length !== 12 || tag.length !== 16)
    throw new Error("Invalid ciphertext format");
  const decipher = createDecipheriv(ALGO, key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(data), decipher.final()]).toString("utf8");
}
