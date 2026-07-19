import hashlib
import hmac
import json
import os
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.utils import timezone

from obe.secure_exam.models import ExamSession


def is_participant_in_active_exam(participant_id: str) -> bool:
    now = timezone.now()
    return ExamSession.objects.filter(
        participant_id=participant_id,
        state__in=["active", "reconnected"],
        starts_at__lte=now,
        ends_at__gte=now,
    ).exists()


def sign_bundle(payload: dict, signing_key: bytes) -> dict:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
    return {
        "payload": b64encode(canonical).decode(),
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "signature": signature,
    }


def verify_bundle(bundle: dict, signing_key: bytes) -> dict:
    canonical = b64decode(bundle["payload"], validate=True)
    checksum = hashlib.sha256(canonical).hexdigest()
    signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(checksum, bundle["sha256"]):
        raise ValueError("Checksum bundle tidak cocok")
    if not hmac.compare_digest(signature, bundle["signature"]):
        raise ValueError("Signature bundle tidak valid")
    return json.loads(canonical)


def encrypt_bundle(payload: dict, encryption_key: bytes, signing_key: bytes) -> dict:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    nonce = os.urandom(12)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, canonical, b"obe-exam-bundle-v1")
    signed = nonce + ciphertext
    return {
        "schema_version": "1.0",
        "nonce": b64encode(nonce).decode(),
        "ciphertext": b64encode(ciphertext).decode(),
        "sha256": hashlib.sha256(signed).hexdigest(),
        "signature": hmac.new(signing_key, signed, hashlib.sha256).hexdigest(),
    }


def decrypt_bundle(bundle: dict, encryption_key: bytes, signing_key: bytes) -> dict:
    nonce = b64decode(bundle["nonce"], validate=True)
    ciphertext = b64decode(bundle["ciphertext"], validate=True)
    signed = nonce + ciphertext
    if not hmac.compare_digest(hashlib.sha256(signed).hexdigest(), bundle["sha256"]):
        raise ValueError("Checksum encrypted bundle tidak cocok")
    expected = hmac.new(signing_key, signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, bundle["signature"]):
        raise ValueError("Signature encrypted bundle tidak valid")
    plaintext = AESGCM(encryption_key).decrypt(nonce, ciphertext, b"obe-exam-bundle-v1")
    return json.loads(plaintext)
