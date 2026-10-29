_kiwi = None


def split_sentences(text: str) -> list[str]:
    """Split Korean text into sentences with kiwipiepy (the model is loaded lazily, once, since loading is slow)."""
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi

        _kiwi = Kiwi()
    return [sentence.text for sentence in _kiwi.split_into_sents(text)]
