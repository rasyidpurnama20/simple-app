import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from obe.secure_exam.services import decrypt_bundle, encrypt_bundle, sign_bundle, verify_bundle


def test_bundle_round_trip():
    payload = {"bundle_id": "EXAM-1", "schema_version": "1.0", "roster_hash": "abc"}
    bundle = sign_bundle(payload, b"secret")
    assert verify_bundle(bundle, b"secret") == payload


def test_bundle_rejects_wrong_key():
    bundle = sign_bundle({"bundle_id": "EXAM-1"}, b"correct")
    with pytest.raises(ValueError, match="Signature"):
        verify_bundle(bundle, b"wrong")


def test_bundle_accepts_previous_key_during_zero_downtime_rotation():
    bundle = sign_bundle({"bundle_id": "EXAM-ROTATION"}, b"previous-key")
    assert verify_bundle(bundle, b"current-key", [b"previous-key"])["bundle_id"] == "EXAM-ROTATION"


def test_bundle_rejects_tamper():
    bundle = sign_bundle({"bundle_id": "EXAM-1"}, b"secret")
    bundle["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Checksum"):
        verify_bundle(bundle, b"secret")


def test_encrypted_bundle_round_trip_and_tamper():
    encryption_key = AESGCM.generate_key(bit_length=256)
    bundle = encrypt_bundle({"bundle_id": "EXAM-2", "items": [1, 2]}, encryption_key, b"sign")
    assert decrypt_bundle(bundle, encryption_key, b"sign")["items"] == [1, 2]
    bundle["signature"] = "0" * 64
    with pytest.raises(ValueError, match="Signature"):
        decrypt_bundle(bundle, encryption_key, b"sign")


def test_encrypted_bundle_accepts_previous_signing_key_during_rotation():
    encryption_key = AESGCM.generate_key(bit_length=256)
    bundle = encrypt_bundle({"bundle_id": "EXAM-3"}, encryption_key, b"previous-signing-key")
    assert (
        decrypt_bundle(bundle, encryption_key, b"current-signing-key", [b"previous-signing-key"])[
            "bundle_id"
        ]
        == "EXAM-3"
    )
