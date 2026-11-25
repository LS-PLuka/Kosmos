"""Foundation checks for the Kosmos package."""


def test_package_is_importable() -> None:
    import kosmos

    assert kosmos.__version__ == "0.1.0"
