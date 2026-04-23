# Ukrposhta Address Matcher

Windows-ready CLI for transforming Ukrposhta registry TXT files into classifier-aligned output with JSON addresses.

## Features

- Reads registry files with `10` or `11` fields separated by `;`
- Verifies postcode first and locks it when classifier confirms it
- Resolves city, street, and house against Ukrposhta address classifier XML API
- Uses local `SQLite` response cache and final resolution cache
- Optionally uses Gemini only as a normalization fallback
- Produces a transformed registry file and `report.csv`
- Supports scheduled cache refresh using configurable hour/minute values from `.env`

## Windows setup

1. Install Python 3.11 or newer and make sure `python` works in PowerShell.
2. Create a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install the package:

```powershell
pip install -e .
```

4. Copy environment settings if needed:

```powershell
Copy-Item .env.example .env
```

## Configuration

Environment variables are read from `.env`.

- `UKRPOSHTA_BEARER_TOKEN`
- `GEMINI_API_KEY`
- `CLASSIFIER_REFRESH_HOUR`
- `CLASSIFIER_REFRESH_MINUTE`
- `CLASSIFIER_REFRESH_TZ`
- `GITHUB_USERNAME`

## Commands

Transform a registry:

```powershell
python -m ukrposhta_address_matcher match-registry "C:\path\input.txt" "C:\path\output.txt" --report "C:\path\report.csv" --cache ".\cache.sqlite"
```

Refresh cached classifier responses:

```powershell
python -m ukrposhta_address_matcher refresh-cache --cache ".\cache.sqlite"
```

## Output contract

Field `4` becomes a compact JSON object:

```json
{"postcode":"","region":"","district":"","city":"","street":"","houseNumber":"","apartmentNumber":""}
```

Fields `postcode`, `region`, `city`, `street`, and `houseNumber` are always populated in output.

## Windows Task Scheduler

Run a daily refresh with values sourced from `.env`:

```powershell
python -m ukrposhta_address_matcher refresh-cache --cache ".\cache.sqlite"
```

Configure the task to run daily at `CLASSIFIER_REFRESH_HOUR:CLASSIFIER_REFRESH_MINUTE`.

## Git

Suggested repository name:

- `mykhailyk/ukrposhta-address-matcher`

## Notes

- Gemini is never a source of truth for the final address.
- The Ukrposhta classifier API remains the canonical source of final structured output.

