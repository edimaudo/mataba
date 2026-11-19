import Dexie, { type Table } from 'dexie';
import type { FolderRecord, ReferenceRecord, ReviewRecord } from '../types';

export type PiiVaultKeyRecord = {
  id: string;
  userId: string;
  key: CryptoKey;
};

export type PiiVaultEntry = {
  id: string;
  userId: string;
  documentId: string;
  iv: Uint8Array;
  ciphertext: ArrayBuffer;
  updatedAt: number;
};

class MatabaLocalDatabase extends Dexie {
  reviews!: Table<ReviewRecord, string>;
  references!: Table<ReferenceRecord, string>;
  folders!: Table<FolderRecord, string>;
  piiVaultKeys!: Table<PiiVaultKeyRecord, string>;
  piiVaultEntries!: Table<PiiVaultEntry, string>;

  constructor() {
    super('mataba-local');
    this.version(1).stores({
      reviews: 'id,userId,updatedAt,contractType,folderId',
      references: 'id,userId,createdAt,folderId',
      folders: 'id,userId,kind',
    });
    this.version(2).stores({
      reviews: 'id,userId,updatedAt,contractType,folderId',
      references: 'id,userId,createdAt,folderId',
      folders: 'id,userId,kind',
      piiVaultKeys: 'id,userId',
      piiVaultEntries: 'id,userId,documentId,updatedAt',
    });
  }
}

export const localDb = new MatabaLocalDatabase();

export async function clearLocalDatabase(): Promise<void> {
  await Promise.all([
    localDb.reviews.clear(),
    localDb.references.clear(),
    localDb.folders.clear(),
    localDb.piiVaultEntries.clear(),
    localDb.piiVaultKeys.clear(),
  ]);
}

/** Remove only the signed-in user's local records after successful account deletion. */
export async function clearUserLocalData(userId: string): Promise<void> {
  await Promise.all([
    localDb.reviews.where('userId').equals(userId).delete(),
    localDb.references.where('userId').equals(userId).delete(),
    localDb.folders.where('userId').equals(userId).delete(),
    localDb.piiVaultEntries.where('userId').equals(userId).delete(),
    localDb.piiVaultKeys.where('userId').equals(userId).delete(),
  ]);
}
