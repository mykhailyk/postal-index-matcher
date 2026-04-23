from ukrposhta_address_matcher.parser import parse_raw_address


def test_parse_address_with_apartment_and_city_marker() -> None:
    parsed = parse_raw_address(
        "\u0432\u0443\u043b. \u041c\u0435\u0447\u043d\u0438\u043a\u043e\u0432\u0430, 11, \u043a\u0432. 12, \u043c\u0456\u0441\u0442\u043e \u0414\u043d\u0456\u043f\u0440\u043e, \u0414\u043d\u0456\u043f\u0440\u043e\u043f\u0435\u0442\u0440\u043e\u0432\u0441\u044c\u043a\u0430 \u043e\u0431\u043b\u0430\u0441\u0442\u044c",
        "49000",
    )
    assert parsed.postcode == "49000"
    assert parsed.city == "\u0414\u043d\u0456\u043f\u0440\u043e"
    assert parsed.street == "\u041c\u0435\u0447\u043d\u0438\u043a\u043e\u0432\u0430"
    assert parsed.house_number == "11"
    assert parsed.apartment_number == "12"


def test_parse_address_strips_extras() -> None:
    parsed = parse_raw_address(
        "\u0432\u0443\u043b \u0420\u043e\u0441\u0442\u0438\u0441\u043b\u0430\u0432\u0441\u044c\u043a\u0430 5\u0431, \u0416\u041a \u0406\u043b\u0456\u0437\u0456\u0443\u043c, \u043c\u0456\u0441\u0442\u043e \u041a\u0438\u0457\u0432",
        "04116",
    )
    assert parsed.city == "\u041a\u0438\u0457\u0432"
    assert parsed.street == "\u0420\u043e\u0441\u0442\u0438\u0441\u043b\u0430\u0432\u0441\u044c\u043a\u0430"
    assert parsed.house_number == "5\u0411"
    assert "\u0416\u041a \u0406\u043b\u0456\u0437\u0456\u0443\u043c" in parsed.extras
