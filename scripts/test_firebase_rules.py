#!/usr/bin/env python3
"""Run Firestore/Storage rules acceptance checks against running Firebase emulators.

Start the Auth, Firestore and Storage emulators with the Firebase CLI, then run this
Python script. The actual test requests and assertions are Python/httpx; no JS test
runner or @firebase/rules-unit-testing package is used.
"""
from __future__ import annotations

import os
import sys
import uuid
from urllib.parse import quote

import httpx

PROJECT_ID = os.getenv("GCLOUD_PROJECT", os.getenv("FIREBASE_PROJECT_ID", "demo-mataba-rules"))
AUTH_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
FIRESTORE_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8081")
STORAGE_HOST = os.getenv("FIREBASE_STORAGE_EMULATOR_HOST", "127.0.0.1:9199")
BUCKET = os.getenv("MATAB_STORAGE_BUCKET", f"{PROJECT_ID}.appspot.com")


def host_url(value: str) -> str:
    return value if value.startswith("http://") or value.startswith("https://") else f"http://{value}"


def sign_up(client: httpx.Client, label: str) -> tuple[str, str]:
    response = client.post(
        f"{host_url(AUTH_HOST)}/identitytoolkit.googleapis.com/v1/accounts:signUp",
        params={"key": "fake-api-key"},
        json={
            "email": f"{label}-{uuid.uuid4().hex[:8]}@example.test",
            "password": "Mataba-Test-Password-123!",
            "returnSecureToken": True,
        },
    )
    response.raise_for_status()
    body = response.json()
    return body["localId"], body["idToken"]


def firestore_url(document_path: str) -> str:
    return (
        f"{host_url(FIRESTORE_HOST)}/v1/projects/{PROJECT_ID}/databases/"
        f"%28default%29/documents/{document_path}"
    )


def expect_status(label: str, response: httpx.Response, expected: set[int], passed: list[str]) -> None:
    if response.status_code not in expected:
        raise AssertionError(f"{label}: expected {sorted(expected)}, got {response.status_code}: {response.text[:300]}")
    passed.append(label)


def main() -> int:
    passed: list[str] = []
    with httpx.Client(timeout=15.0) as client:
        try:
            alice_uid, alice_token = sign_up(client, "mataba-alice")
            bob_uid, bob_token = sign_up(client, "mataba-bob")
        except httpx.ConnectError as exc:
            print(
                "Firebase emulators are not available. Start them with: "
                "firebase emulators:start --project demo-mataba-rules --only auth,firestore,storage",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc

        review_path = f"users/{alice_uid}/reviews/review-1"
        create = client.patch(
            firestore_url(review_path),
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"fields": {"userId": {"stringValue": alice_uid}, "title": {"stringValue": "Sanitized review"}}},
        )
        expect_status("Owner can create their own review", create, {200}, passed)

        read_owner = client.get(firestore_url(review_path), headers={"Authorization": f"Bearer {alice_token}"})
        expect_status("Owner can read their review", read_owner, {200}, passed)

        read_other = client.get(firestore_url(review_path), headers={"Authorization": f"Bearer {bob_token}"})
        expect_status("Another user cannot read the owner's review", read_other, {401, 403}, passed)

        forged = client.patch(
            firestore_url(f"users/{alice_uid}/reviews/forged"),
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"fields": {"userId": {"stringValue": bob_uid}}},
        )
        expect_status("Owner cannot forge another userId", forged, {401, 403}, passed)

        unsupported = client.patch(
            firestore_url(f"users/{alice_uid}/unapproved/forged"),
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"fields": {"userId": {"stringValue": alice_uid}}},
        )
        expect_status("Unsupported user collection is rejected", unsupported, {401, 403}, passed)

        anonymous = client.get(firestore_url(review_path))
        expect_status("Anonymous access is rejected", anonymous, {401, 403}, passed)

        delete_owner = client.delete(firestore_url(review_path), headers={"Authorization": f"Bearer {alice_token}"})
        expect_status("Owner can delete their own review", delete_owner, {200, 204}, passed)

        upload = client.post(
            f"{host_url(STORAGE_HOST)}/v0/b/{quote(BUCKET, safe='')}/o",
            params={"uploadType": "media", "name": f"users/{alice_uid}/contracts/original.pdf"},
            headers={"Authorization": f"Bearer {alice_token}", "Content-Type": "application/pdf"},
            content=b"not-a-real-contract",
        )
        expect_status("Client upload to Storage is denied", upload, {401, 403}, passed)

    print(f"Firebase Emulator rules: {len(passed)} Python REST assertions passed.")
    for item in passed:
        print(f"PASS {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
