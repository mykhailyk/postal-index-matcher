from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ukrposhta_address_matcher.models import ParsedAddress


class GeminiFallbackClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def normalize_address(self, raw_address: str, postcode: str) -> ParsedAddress | None:
        if not self.api_key:
            return None
        prompt = (
            "Role: \u0435\u043a\u0441\u043f\u0435\u0440\u0442 \u0437 \u0430\u0434\u0440\u0435\u0441 \u0423\u043a\u0440\u0430\u0457\u043d\u0438 \u0442\u0430 \u043f\u0435\u0440\u0435\u0439\u043c\u0435\u043d\u0443\u0432\u0430\u043d\u044c.\n"
            "Task: \u043f\u0435\u0440\u0435\u0442\u0432\u043e\u0440\u0438 raw_address \u0443 classifier-compatible \u043a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u0438.\n"
            "Rules: \u0432\u0438\u043a\u043e\u0440\u0438\u0441\u0442\u043e\u0432\u0443\u0439 \u0441\u0443\u0447\u0430\u0441\u043d\u0456 \u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0456 \u043d\u0430\u0437\u0432\u0438; \u043d\u0435 \u0432\u0438\u0433\u0430\u0434\u0443\u0439 \u0456\u043d\u0434\u0435\u043a\u0441; \u0456\u0433\u043d\u043e\u0440\u0443\u0439 \u0416\u041a/\u043e\u0444\u0456\u0441\u0438/\u0441\u043b\u0443\u0436\u0431\u043e\u0432\u0456 \u0445\u0432\u043e\u0441\u0442\u0438; \u044f\u043a\u0449\u043e \u043d\u0435 \u0432\u043f\u0435\u0432\u043d\u0435\u043d\u0438\u0439 - \u043f\u043e\u0432\u0435\u0440\u0442\u0430\u0439 \u043f\u043e\u0440\u043e\u0436\u043d\u0456 \u043f\u043e\u043b\u044f.\n"
            "Output only JSON:\n"
            '{"region":"","district":"","city":"","street":"","houseNumber":"","apartmentNumber":"","renameHints":[],"confidence":""}\n'
            f"postcode={postcode}\n"
            f"raw_address={raw_address}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-lite:generateContent?"
            + urlencode({"key": self.api_key})
        )
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))

        text = ""
        for candidate in payload.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]
        text = text.strip().strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return ParsedAddress(
            postcode=postcode,
            region=str(parsed.get("region", "")),
            district=str(parsed.get("district", "")),
            city=str(parsed.get("city", "")),
            street=str(parsed.get("street", "")),
            house_number=str(parsed.get("houseNumber", "")),
            apartment_number=str(parsed.get("apartmentNumber", "")),
        )
