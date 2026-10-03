from backend.app.services.passwords import hash_password, verify_password


def test_hashes_and_verifies_password() -> None:
    stored_hash = hash_password("Correct-Horse-27")

    assert stored_hash != "Correct-Horse-27"
    assert stored_hash.startswith("$argon2id$")
    assert verify_password("Correct-Horse-27", stored_hash) is True
    assert verify_password("wrong-password", stored_hash) is False


def test_same_password_gets_different_salts() -> None:
    first_hash = hash_password("Correct-Horse-27")
    second_hash = hash_password("Correct-Horse-27")

    assert first_hash != second_hash


def test_unrecognized_hash_is_rejected() -> None:
    assert verify_password("Correct-Horse-27", "not-a-password-hash") is False
