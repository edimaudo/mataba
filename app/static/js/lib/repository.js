import { collection, deleteDoc, doc, getDocs, orderBy, query, serverTimestamp, setDoc, writeBatch, } from 'firebase/firestore';
import { deleteObject, listAll, ref as storageRef } from 'firebase/storage';
import { deleteUser, EmailAuthProvider, reauthenticateWithCredential } from 'firebase/auth';
import { auth, db, firebaseConfigured, storage } from './firebase.js';
import { clearUserLocalData, localDb } from './localDb.js';
function omitUndefined(value) {
    if (Array.isArray(value))
        return value.map(omitUndefined);
    if (value && typeof value === 'object') {
        const prototype = Object.getPrototypeOf(value);
        if (prototype === Object.prototype || prototype === null) {
            return Object.fromEntries(Object.entries(value)
                .filter(([, child]) => child !== undefined)
                .map(([key, child]) => [key, omitUndefined(child)]));
        }
    }
    return value;
}
function isCloudUser(userId) {
    return firebaseConfigured && Boolean(db) && userId !== 'preview';
}
export async function listReviews(userId) {
    if (isCloudUser(userId)) {
        try {
            const ref = collection(db, 'users', userId, 'reviews');
            const snapshot = await getDocs(query(ref, orderBy('updatedAt', 'desc')));
            const items = snapshot.docs.map((item) => ({ ...item.data(), id: item.id }));
            await localDb.reviews.bulkPut(items);
            return items;
        }
        catch {
            // Local cache keeps prior sanitized reviews available during an outage.
        }
    }
    const cached = await localDb.reviews.where('userId').equals(userId).toArray();
    return cached.sort((a, b) => b.updatedAt - a.updatedAt);
}
export async function saveReview(review) {
    await localDb.reviews.put(review);
    if (!isCloudUser(review.userId))
        return;
    const ref = doc(db, 'users', review.userId, 'reviews', review.id);
    const payload = omitUndefined({
        ...review,
        updatedAt: review.updatedAt,
        createdAt: review.createdAt,
        // Original files and reversible PII token maps are never written to Firestore.
        originalFileStored: false,
        piiVaultStored: false,
    });
    await setDoc(ref, { ...payload, serverUpdatedAt: serverTimestamp() }, { merge: true });
}
export async function deleteReview(userId, reviewId) {
    await localDb.reviews.delete(reviewId);
    if (isCloudUser(userId))
        await deleteDoc(doc(db, 'users', userId, 'reviews', reviewId));
}
export async function listReferences(userId) {
    if (isCloudUser(userId)) {
        try {
            const ref = collection(db, 'users', userId, 'references');
            const snapshot = await getDocs(query(ref, orderBy('createdAt', 'desc')));
            const items = snapshot.docs.map((item) => ({ ...item.data(), id: item.id }));
            await localDb.references.bulkPut(items);
            return items;
        }
        catch {
            // Return the last local cache below.
        }
    }
    const cached = await localDb.references.where('userId').equals(userId).toArray();
    return cached.sort((a, b) => b.createdAt - a.createdAt);
}
export async function saveReference(reference) {
    await localDb.references.put(reference);
    if (!isCloudUser(reference.userId))
        return;
    const payload = omitUndefined({
        ...reference,
        // These are PII-sanitized page extracts, not the uploaded source file.
        originalFileStored: false,
    });
    await setDoc(doc(db, 'users', reference.userId, 'references', reference.id), payload);
}
export async function deleteReference(userId, referenceId) {
    await localDb.references.delete(referenceId);
    if (isCloudUser(userId))
        await deleteDoc(doc(db, 'users', userId, 'references', referenceId));
}
export async function listFolders(userId) {
    if (isCloudUser(userId)) {
        try {
            const ref = collection(db, 'users', userId, 'folders');
            const snapshot = await getDocs(query(ref, orderBy('createdAt', 'asc')));
            const items = snapshot.docs.map((item) => ({ ...item.data(), id: item.id }));
            await localDb.folders.bulkPut(items);
            return items;
        }
        catch {
            // Use local cache if Firestore is offline.
        }
    }
    return localDb.folders.where('userId').equals(userId).toArray();
}
export async function saveFolder(folder) {
    await localDb.folders.put(folder);
    if (!isCloudUser(folder.userId))
        return;
    await setDoc(doc(db, 'users', folder.userId, 'folders', folder.id), omitUndefined(folder));
}
export async function purgeAndDeleteAccount(userId, password) {
    const currentUser = auth?.currentUser;
    if (!currentUser || currentUser.uid !== userId || !db) {
        throw new Error('You must be signed in to delete this account.');
    }
    if (!currentUser.email || !password) {
        throw new Error('Re-enter your account password before deleting your account.');
    }
    // Reauthenticate before the first destructive operation. Firebase Auth may
    // reject deleteUser() when the session is not recent; doing this first avoids
    // deleting customer records and then leaving an undeleted account behind.
    const credential = EmailAuthProvider.credential(currentUser.email, password);
    try {
        await reauthenticateWithCredential(currentUser, credential);
    }
    catch {
        throw new Error('Account verification failed. Check your password and try again.');
    }
    // All persistent user records currently live in these known subcollections.
    // The sequence is idempotent: a retry can continue after a partial purge.
    for (const subcollection of ['reviews', 'references', 'folders']) {
        const snapshot = await getDocs(collection(db, 'users', userId, subcollection));
        for (let offset = 0; offset < snapshot.docs.length; offset += 450) {
            const batch = writeBatch(db);
            snapshot.docs.slice(offset, offset + 450).forEach((item) => batch.delete(item.ref));
            await batch.commit();
        }
    }
    if (storage) {
        const prefix = storageRef(storage, `users/${userId}`);
        await deleteStorageTree(prefix);
    }
    await deleteDoc(doc(db, 'users', userId));
    // Clear local documents and the reversible PII vault before removing the
    // Auth identity, so a final Auth deletion failure cannot leave local PII.
    await clearUserLocalData(userId);
    await deleteUser(currentUser);
}
async function deleteStorageTree(directoryRef) {
    const listing = await listAll(directoryRef);
    await Promise.all(listing.items.map((item) => deleteObject(item)));
    await Promise.all(listing.prefixes.map((prefix) => deleteStorageTree(prefix)));
}
export async function createDocumentId() {
    // Random UUIDs are generated in the browser; the original content is not used as an ID.
    return crypto.randomUUID();
}
