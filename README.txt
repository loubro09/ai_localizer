# Installation och körning

## Krav

Innan du börjar behöver du:

- Python 3 installerat
- Visual Studio Code eller annan kodeditor
- En OpenAI API-nyckel
- Internetanslutning

## 1. Klona eller öppna projektet

Om du redan har projektmappen, öppna den i terminalen eller i Visual Studio Code.

## 2. Skapa en .env-fil

Skapa en fil som heter .env i projektets rotmapp.
Innehåll:

OPENAI_API_KEY=din_api_nyckel_här

Aktivera useEnv i settings.

## 3. Kontrollera att Python 3 finns installerat

Öppna Terminal och kör:

i MacOS: python3 --version
i Windows: python --version

## 4. Skapa ett virtuellt environment

I projektmappen, kör:

i MacOS: python3 -m venv .venv
i Windows: python -m venv .venv

## 5. Aktivera environment

i MacOS: source .venv/bin/activate
i Windows: .venv\Scripts\activate ELLER .venv\Scripts\Activate.ps1

## 6. Installera beroenden

Projektet använder dessa Python-paket:

fastapi
uvicorn
python-multipart
openai
pydantic
python-dotenv

Du kan installera dem i terminalen:

pip install -r requirements.txt

## 7. Starta servern

uvicorn main:app --reload

## 8. Öppna programmet i webbläsaren

Gå till:

http://127.0.0.1:8000
