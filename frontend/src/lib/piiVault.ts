import { localDb, type PiiVaultEntry, type PiiVaultKeyRecord } from './localDb';

const KEY_PREFIX = 'pii-vault-key:';
const ENTRY_PREFIX = 'pii-vault-entry:';
const encoder = new TextEncoder();
const decoder = new TextDecoder();

function keyId(userId: string): string {
  return `${KEY_PREFIX}${userId}`;
}

function entryId(userId: string, documentId: string): string {
  return `${ENTRY_PREFIX}${userId}:${documentId}`;
}

async function getOrCreateKey(userId: string): Promise<CryptoKey> {
  const id = keyId(userId);
  const existing = await localDb.piiVaultKeys.get(id);
  if (existing?.key) return existing.key;

  if (!globalThis.crypto?.subtle) {
    throw new Error('This browser does not support encrypted local privacy storage.');
  }
  const key = await crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
  const record: PiiVaultKeyRecord = { id, userId, key };
  await localDb.piiVaultKeys.put(record);
  return key;
}

/** Persist reversible tokens as AES-GCM ciphertext in IndexedDB, never Firestore. */
export async function savePiiTokenMap(
  userId: string,
  documentId: string,
  tokenMap: Record<string, string>,
): Promise<void> {
  const id = entryId(userId, documentId);
  if (!Object.keys(tokenMap).length) {
    await localDb.piiVaultEntries.delete(id);
    return;
  }

  const key = await getOrCreateKey(userId);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const additionalData = encoder.encode(`${userId}:${documentId}`);
  const plaintext = encoder.encode(JSON.stringify(tokenMap));
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData },
    key,
    plaintext,
  );
  const record: PiiVaultEntry = {
    id,
    userId,
    documentId,
    iv,
    ciphertext,
    updatedAt: Date.now(),
  };
  await localDb.piiVaultEntries.put(record);
}

export async function loadPiiTokenMap(
  userId: string,
  documentId: string,
): Promise<Record<string, string>> {
  const record = await localDb.piiVaultEntries.get(entryId(userId, documentId));
  if (!record) return {};
  const keyRecord = await localDb.piiVaultKeys.get(keyId(userId));
  if (!keyRecord?.key) {
    throw new Error('The local privacy key is unavailable. Original values cannot be restored on this device.');
  }
  try {
    const additionalData = encoder.encode(`${userId}:${documentId}`);
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: record.iv, additionalData },
      keyRecord.key,
      record.ciphertext,
    );
    const parsed: unknown = JSON.parse(decoder.decode(plaintext));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([token, value]) => token.startsWith('[') && typeof value === 'string'),
    );
  } catch {
    throw new Error('The encrypted local privacy data could not be opened. Saved sanitized reports remain available.');
  }
}

export async function deletePiiTokenMap(userId: string, documentId: string): Promise<void> {
  await localDb.piiVaultEntries.delete(entryId(userId, documentId));
}

export async function clearUserPiiVault(userId: string): Promise<void> {
  await localDb.transaction('rw', localDb.piiVaultKeys, localDb.piiVaultEntries, async () => {
    await localDb.piiVaultEntries.where('userId').equals(userId).delete();
    await localDb.piiVaultKeys.where('userId').equals(userId).delete();
  });
}
