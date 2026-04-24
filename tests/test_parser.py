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


def test_parse_address_location_tail_without_city_marker() -> None:
    parsed = parse_raw_address(
        "\u0432\u0443\u043b.\u0421\u0442\u0435\u043f\u043e\u0432\u0430, \u0431\u0443\u0434.1, \u043a\u0432. \u0417\u043e\u0440\u044f \u041a\u0440\u0438\u043d\u0438\u0447\u0430\u043d\u0441\u044c\u043a\u0438\u0439 \u0414\u043d\u0456\u043f\u0440\u043e\u043f\u0435\u0442\u0440\u043e\u0432\u0441\u044c\u043a\u0430",
        "52339",
    )
    assert parsed.city == "\u0417\u043e\u0440\u044f"
    assert parsed.district == "\u041a\u0440\u0438\u043d\u0438\u0447\u0430\u043d\u0441\u044c\u043a\u0438\u0439"
    assert parsed.region == "\u0414\u043d\u0456\u043f\u0440\u043e\u043f\u0435\u0442\u0440\u043e\u0432\u0441\u044c\u043a\u0430"
    assert parsed.street == "\u0421\u0442\u0435\u043f\u043e\u0432\u0430"
    assert parsed.house_number == "1"


def test_parse_address_with_apartment_stuck_to_city_tail() -> None:
    parsed = parse_raw_address(
        "\u0432\u0443\u043b.\u0421\u0432\u043e\u0431\u043e\u0434\u0438, \u0431\u0443\u0434.35, \u043a\u0432.16 \u0423\u0436\u0433\u043e\u0440\u043e\u0434 \u0417\u0430\u043a\u0430\u0440\u043f\u0430\u0442\u0441\u044c\u043a\u0430",
        "88000",
    )
    assert parsed.city == "\u0423\u0436\u0433\u043e\u0440\u043e\u0434"
    assert parsed.region == "\u0417\u0430\u043a\u0430\u0440\u043f\u0430\u0442\u0441\u044c\u043a\u0430"
    assert parsed.street == "\u0421\u0432\u043e\u0431\u043e\u0434\u0438"
    assert parsed.house_number == "35"
    assert parsed.apartment_number == "16"


def test_parse_address_handles_compact_city_marker_and_house_in_street_token() -> None:
    parsed = parse_raw_address(
        "\u0432\u0443\u043b.\u041a\u043e\u043c\u0456\u043d\u0442\u0435\u0440\u043d\u0430, 41, \u043c.\u0412\u0430\u0441\u0438\u043b\u044c\u043a\u0456\u0432, \u041a\u0438\u0457\u0432\u0441\u044c\u043a\u0430 \u043e\u0431\u043b\u0430\u0441\u0442\u044c",
        "08600",
    )
    assert parsed.city == "\u0412\u0430\u0441\u0438\u043b\u044c\u043a\u0456\u0432"
    assert parsed.region == "\u041a\u0438\u0457\u0432\u0441\u044c\u043a\u0430"
    assert parsed.street == "\u041a\u043e\u043c\u0456\u043d\u0442\u0435\u0440\u043d\u0430"
    assert parsed.house_number == "41"


def test_parse_address_handles_house_embedded_in_street_token() -> None:
    parsed = parse_raw_address(
        "\u0432\u0443\u043b. \u041c\u0438\u043a\u043e\u043b\u0438 \u041a\u0438\u0431\u0430\u043b\u044c\u0447\u0438\u0447\u0430 2\u0410, \u043c\u0456\u0441\u0442\u043e \u041a\u0438\u0457\u0432",
        "02218",
    )
    assert parsed.city == "\u041a\u0438\u0457\u0432"
    assert parsed.street == "\u041c\u0438\u043a\u043e\u043b\u0438 \u041a\u0438\u0431\u0430\u043b\u044c\u0447\u0438\u0447\u0430"
    assert parsed.house_number == "2\u0410"


def test_parse_address_extracts_office_and_room_numbers() -> None:
    office_parsed = parse_raw_address(
        "\u0432\u0443\u043b. \u0414\u0430\u043b\u044c\u043d\u0438\u0446\u044c\u043a\u0430 \u0431. 25/2, \u043e\u0444.203, \u041e\u0434\u0435\u0441\u0430, \u041e\u0434\u0435\u0441\u044c\u043a\u0430 \u043e\u0431\u043b\u0430\u0441\u0442\u044c",
        "65005",
    )
    room_parsed = parse_raw_address(
        "\u0443\u043b \u041a\u0438\u0440\u0438\u043b\u043b\u043e\u0432\u0441\u043a\u0430\u044f, 69-\u0412, \u043a\u043e\u043c\u043d\u0430\u0442\u0430 117, \u043c\u0456\u0441\u0442\u043e \u041a\u0438\u0457\u0432",
        "04080",
    )
    assert office_parsed.street == "\u0414\u0430\u043b\u044c\u043d\u0438\u0446\u044c\u043a\u0430"
    assert office_parsed.house_number == "25/2"
    assert office_parsed.apartment_number == "203"
    assert room_parsed.street == "\u041a\u0438\u0440\u0438\u043b\u043b\u043e\u0432\u0441\u043a\u0430\u044f"
    assert room_parsed.house_number == "69-\u0412"
    assert room_parsed.apartment_number == "117"


def test_parse_address_detects_po_box() -> None:
    parsed = parse_raw_address(
        "\u0430/\u0441 5283, \u041b\u044c\u0432\u0456\u0432, \u041b\u044c\u0432\u0456\u0432\u0441\u044c\u043a\u0430 \u043e\u0431\u043b\u0430\u0441\u0442\u044c",
        "79010",
    )
    assert parsed.city == "\u041b\u044c\u0432\u0456\u0432"
    assert parsed.region == "\u041b\u044c\u0432\u0456\u0432\u0441\u044c\u043a\u0430"
    assert parsed.po_box_number == "5283"
    assert parsed.street == ""
    assert parsed.house_number == ""
