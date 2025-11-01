from lightkube import operators


def test_exists():
    assert operators.exists().encode("key") == "key"


def test_not_exists():
    assert operators.not_exists().encode("key") == "!key"


def test_equal():
    assert operators.equal("xxx").encode("key") == "key=xxx"


def test_not_equal():
    assert operators.not_equal("xxx").encode("key") == "key!=xxx"


def test_in():
    assert operators.in_(["xxx", "yyy"]).encode("key") == "key in (xxx,yyy)"


def test_not_in():
    assert operators.not_in(["xxx", "zzz"]).encode("key") == "key notin (xxx,zzz)"
