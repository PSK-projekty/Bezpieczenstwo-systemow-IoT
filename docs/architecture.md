# Architektura systemu IoT

## Diagramy PlantUML

Kod zrodlowy diagramow znajduje sie w katalogu `docs/diagrams`:

- `component.puml` - widok komponentow systemu,
- `device_telemetry_sequence.puml` - sekwencja wysylki odczytu z urzadzenia.

Aby wygenerowac grafiki, zainstaluj PlantUML i uruchom:

```bash
plantuml docs/diagrams/*.puml
```

Obrazy (`.png` lub `.svg`) pojawia sie obok plikow `.puml`. Wiele IDE (np. VS Code z rozszerzeniem PlantUML) pozwala podgladac diagramy bezposrednio podczas edycji.

## Ogolny obraz

System sklada sie z kompaktowego backendu FastAPI (Python 3.12), ktory korzysta z nastepujacych warstw:

- **API (FastAPI)** - definicja tras REST oraz zaleznosci odpowiedzialnych za autoryzacje.
- **Serwisy domenowe** - enkapsuluja logike biznesowa (autoryzacja, urzadzenia, odczyty, logi).
- **Modele SQLAlchemy** - odwzorowanie encji w relacyjnej bazie SQLite.
- **Schematy Pydantic** - walidacja danych wejsciowych/wyjsciowych oraz jawne kontrakty API.
- **Logi bezpieczenstwa** - osobna tabela na zdarzenia (sukcesy, odmowy, bledy).
- **Front-end PyQt5** - aplikacja desktopowa korzystajaca z REST API (autoryzacja, dane, logi).

Calosc uruchamiana jest poleceniem `uvicorn app.main:app --reload`, ktore wykonyje:

1. Tworzenie schematu bazy (`Base.metadata.create_all`).
2. Upewnienie sie, ze istnieje konto administratora (bootstrap).
3. Rejestracje routerow API oraz start symulatora telemetrii.

## Warstwa danych

| Encja | Najwazniejsze pola | Uwagi |
| --- | --- | --- |
| `User` | `email`, `password_hash`, `role`, `created_at` | Role: `user`, `admin`; hasla w bcrypt |
| `Device` | `name`, `owner_id`, `status`, `secret_hash`, `token_version`, `last_reading_at` | `token_version` uniewaznia tokeny przy rotacji sekretu |
| `RefreshToken` | `token_jti`, `token_hash`, `expires_at`, `revoked` | Jeden aktywny token per uzytkownik, przechowywany jako skrot |
| `Reading` | `device_id`, `payload`, `payload_size`, `device_timestamp`, `received_at` | Wymuszone limity rozmiaru i czestotliwosci |
| `SecurityEvent` | `actor_type`, `actor_id`, `event_type`, `status`, `detail` | Dostepne dla administratora, zrodlo audytu |

SQLite wybrano ze wzgledu na prosty start i przenosnosc. Kod nie korzysta z dialektowych rozszerzen, wiec migracja do PostgreSQL ogranicza sie do zmiany `DATABASE_URL`.

## Kluczowe przeplywy

1. **Onboarding uzytkownika**  
   Rejestracja (`/auth/register`) -> Logowanie (`/auth/login`) -> Odbior tokenow -> (opcjonalnie) odswiezanie (`/auth/refresh`) -> Wylogowanie (`/auth/logout`).

2. **Provisioning urzadzenia**  
   Uzytkownik tworzy urzadzenie (`/devices`) -> otrzymuje jednorazowy sekret -> przenosi dane do firmware.

3. **Uwierzytelnienie urzadzenia**  
   Urzadzenie wymienia `device_id + secret` na token (`/device/token`) -> token zawiera `token_version`, dzieki czemu rotacja sekretu natychmiast uniewaznia stare tokeny.

4. **Wysylka danych**  
   Urzadzenie wysyla odczyty (`/device/readings`) -> system kontroluje limity (rozmiar, czestotliwosc) i zapisuje metadane (`received_at`, `payload_size`).

5. **Odczyt danych przez wlasciciela**  
   Uzytkownik filtruje odczyty (`/devices/{id}/readings`) lub pobiera metadane (`/devices/{id}/readings/meta`). Administrator widzi wszystkie urzadzenia.

6. **Incydent bezpieczenstwa**  
   Uzytkownik blokuje urzadzenie (`/devices/{id}/deactivate`) lub rotuje sekret (`/devices/{id}/rotate-secret`). W obu przypadkach tokeny staja sie niewazne.

## Zabezpieczenia i dobre praktyki

- Oddzielne klucze JWT dla ludzi (`JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`) oraz urzadzen (`JWT_DEVICE_SECRET_KEY`).
- Krotki TTL tokenow: dla uzytkownika ~15 min, dla urzadzenia ~5 min, odswiezanie tylko z waznym refresh tokenem zapisanym w bazie.
- Hashowanie hasel i sekretow urzadzen przy uzyciu `passlib[bcrypt]`.
- Rate limiting: `last_reading_at` zapobiega zalewaniu endpointu przez urzadzenie.
- Kontrola rozmiaru payloadu przed zapisem - brak nielimitowanych struktur JSON.
- Logi zdarzen - kazdy sukces/odmowa zapisywany w `SecurityEvent` (widok administracyjny `/admin/security-events`).
- Krotkie komunikaty bledow w jezyku polskim bez ujawniania szczegolow implementacyjnych.
- Domyslny administrator tworzony przy starcie - dane mozna zmienic w `.env`.

## Scenariusze awaryjne i rozszerzenia

- W przypadku utraty sekretu urzadzenia wlasciciel moze natychmiast rotowac sekret lub zablokowac urzadzenie; tokeny przestana dzialac dzieki inkrementacji `token_version`.
- W przypadku kradziezy refresh tokenu wystarczy wylogowac sie (`/auth/logout`), co uniewaznia wpis w tabeli `refresh_tokens`.
- Logi pozwalaja odtworzyc proby wlamania (np. zly sekret albo obce urzadzenie).

### Mozliwe usprawnienia

- Podlaczenie systemu kolejkowego (np. RabbitMQ) do akwizycji odczytow i asynchronicznej obrobki.
- Dodanie WebSocketow lub SSE dla podgladu na zywo, bazujac na tych samych serwisach i autoryzacji.
- Wprowadzenie mechanizmu polityk (np. odciecie urzadzenia po N odmowach).
- Wsparcie dla podpisow HMAC w odczytach (dodatkowe zabezpieczenie poza JWT).
- Rozszerzenie panelu PyQt o widoki analityczne oraz konfiguracje limitow po stronie uzytkownika.
