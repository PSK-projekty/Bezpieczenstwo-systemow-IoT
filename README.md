# Demo Bezpieczenstwa IoT

Repozytorium prezentuje kompletny, edukacyjny stos do zarzadzania flota urzadzen IoT. Backend FastAPI udostepnia zabezpieczone JWT-em API, a klient PyQt5 ulatwia obsluge urzadzen, uzytkownikow oraz logow bezpieczenstwa. Projekt powstal na potrzeby zajec z bezpieczenstwa systemow IoT.

## Najwazniejsze mozliwosci

- Uwierzytelnianie oparte na JWT dla ludzi (tokeny dostepu i odswiezania) oraz urzadzen (krotkie tokeny dostepu).
- Katalog urzadzen z piecioma profilami referencyjnymi (stacja pogodowa, termometr, kamera IP, czujnik jakosci powietrza, inteligentny zamek) wraz z przykladowymi payloadami.
- Symulator telemetrii generujacy odczyty zgodnie z profilem urzadzenia, z zachowaniem limitow czestotliwosci i rozmiaru.
- Pelne CRUD: tworzenie, aktualizacja, rotacja sekretow, dezaktywacja i usuwanie urzadzen; panel administracyjny do zarzadzania uzytkownikami.
- Rejestr zdarzen bezpieczenstwa, eksport odczytow do CSV oraz filtrowanie po przedzialach czasowych.

## Struktura katalogow

```
app/
  api/        -> routery FastAPI (auth, devices, device_data, admin, health)
  core/       -> konfiguracja oraz narzedzia kryptograficzne
  db/         -> modele SQLAlchemy i fabryka sesji (SQLite)
  schemas/    -> schematy Pydantic wykorzystywane przez API
  services/   -> logika biznesowa (auth, urzadzenia, odczyty, logowanie, symulator)
docs/         -> dokumentacja i materialy opisowe
gui/          -> aplikacja kliencka PyQt5
data/         -> domyslna baza SQLite (iot_demo.db)
tests/        -> testy jednostkowe i integracyjne
```

## Wymagania i instalacja

1. Zainstaluj Pythona 3.11 lub nowszego.
2. (Opcjonalnie) utworz srodowisko wirtualne:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\activate
   ```
3. Zainstaluj zaleznosci:
   ```bash
   pip install -r requirements.txt
   ```

## Konfiguracja

Zmienne srodowiskowe opisuje plik `.env.example`. Skopiuj go do `.env` i w razie potrzeby dostosuj. Domyslnie aplikacja korzysta z bazy SQLite `./data/iot_demo.db` oraz przykladowych kluczy JWT. Wazniejsze parametry:

- `DATABASE_URL` - sciezka do bazy danych,
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, `JWT_DEVICE_SECRET_KEY` - klucze podpisujace tokeny,
- `ACCESS_TOKEN_EXP_MINUTES`, `REFRESH_TOKEN_EXP_MINUTES`, `DEVICE_TOKEN_EXP_MINUTES` - czasy zycia tokenow,
- limity odczytow (`DATA_PAYLOAD_LIMIT_BYTES`, `MIN_SECONDS_BETWEEN_READINGS`).

## Dokumentacja API

- Swagger UI: http://127.0.0.1:8000/docs
- Redoc: http://127.0.0.1:8000/redoc

## Uruchomienie backendu

```bash
uvicorn app.main:app --reload
```

Podczas startu:

1. SQLAlchemy tworzy wszystkie tabele (Base.metadata.create_all).
2. Jezeli brakuje kolumny `category` w tabeli `devices`, zostaje dodana (prosta pseudo-migracja).
3. `AuthService.ensure_admin_exists()` zaklada domyslne konto administratora (`admin@example.com` / `Admin123!`), o ile w bazie nie ma jeszcze admina.
4. Uruchamiany jest symulator telemetrii dla aktywnych urzadzen.

Przydatne adresy:

- Health check: http://127.0.0.1:8000/healthz

## Klient graficzny (PyQt5)

Uruchomienie:

```bash
python -m gui
```

Klient domyslnie laczy sie z backendem pod adresem http://127.0.0.1:8000. Jezeli API dziala na innej maszynie lub porcie, ustaw zmienna srodowiskowa `IOT_BACKEND_URL`.

Funkcje GUI:

- lista urzadzen ze statusem i szczegolami,
- kreator dodawania urzadzen z podgladem przykladowego payloadu,
- rotacja sekretow i natychmiastowe uniewaznianie tokenow,
- eksport odczytow do CSV i filtrowanie po datach,
- zakladki administracyjne dla roli `admin` (zarzadzanie uzytkownikami, logi bezpieczenstwa).

## Reset bazy danych

Zatrzymaj backend i usun plik `data/iot_demo.db`. Przy kolejnym uruchomieniu serwera baza zostanie utworzona ponownie, a konto administratora odtworzone. Jesli system zwraca blad EBUSY, zamknij wszystkie aplikacje trzymajace otwarte polaczenie z plikiem (backend, edytor, narzedzia SQLite).

## Testy

```bash
pytest
```

Testy korzystaja z bazy SQLite w pamieci oraz wylaczonego symulatora, dzieki czemu sa deterministyczne i pokrywaja m.in. rejestracje, zarzadzanie urzadzeniami oraz uprawnienia administratora.

### Pokrycie testami

Przyklad polecenia:

```bash
pytest --cov=app --cov=gui --cov-report=term
```

Ostatni wynik (Windows, Python 3.12):

```
app/api/...         ~90%
app/services/...    86-94%
gui/api_client.py   83%
gui/app.py          76%
gui/auth_dialog.py  95%
gui/main_window.py  84%
SUMA                89%
```

## JWT w tym projekcie

System korzysta z trzech typow tokenow:

1. **Token dostepu uzytkownika** - podpisany kluczem `JWT_SECRET_KEY`, zawiera identyfikator (`sub`) i role. Wazny krotko (np. 15 minut) i trafia w naglowku `Authorization`.
2. **Token odswiezania uzytkownika** - podpisany `JWT_REFRESH_SECRET_KEY`, wazny nawet kilka dni. Kazde uzycie wydaje nowy komplet tokenow, a poprzedni wpis w tabeli `refresh_tokens` jest uniewazniany.
3. **Token dostepu urzadzenia** - podpisany `JWT_DEVICE_SECRET_KEY`, wazny kilka minut. Firmware wysyla `device_id` i jednorazowy sekret (pokazywany w GUI tylko raz). W bazie przechowywany jest wylacznie hash sekretu (`secret_hash`).

Mechanizmy uzupelniajace:

- rotacja sekretu zwieksza pole `token_version`, co uniewaznia wszystkie stare tokeny urzadzenia,
- endpoint `/device/readings` kontroluje token, wersje oraz limity czestotliwosci i rozmiaru,
- wszystkie proby uwierzytelniania i operacje administracyjne zapisywane sa w tabeli `security_events`.

## Notatki bezpieczenstwa

- Hasla uzytkownikow i sekrety urzadzen sa przechowywane jako hash bcrypt.
- Uprawnienia administratora sa wymuszane przez zaleznosc `require_admin`.
- Limity rozmiaru i czestotliwosci odczytow chronia API przed floodem.
- GUI posiada walidacje danych i czytelne komunikaty bledow, aby zmniejszyc ryzyko pomylek.
