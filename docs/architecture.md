# Architektura systemu IoT

## Ogólny obraz

System składa się z kompaktowego backendu FastAPI (Python 3.12) opartego na warstwach:

- **API (FastAPI)** – definiuje trasy REST oraz zależności (kontrola dostępu).
- **Serwisy domenowe** – enkapsulują logikę biznesową (autoryzacja, urządzenia, odczyty, logi).
- **Modele SQLAlchemy** – odwzorowanie encji w relacyjnej bazie SQLite.
- **Schematy Pydantic** – walidacja wejścia/wyjścia, jawne kontrakty API.
- **Logi bezpieczeństwa** – osobna tabela na zdarzenia (sukcesy, odmowy, błędy).
- **Front-end PyQt5** – aplikacja desktopowa wykorzystująca REST API (autoryzacja, dane, logi).

Całość uruchamiana jest jednym poleceniem `uvicorn app.main:app --reload`, które wykonuje:

1. Tworzenie schematu bazy (`Base.metadata.create_all`).
2. bootstrap konta administratora (o ile brak w bazie).
3. Rejestrację routerów API.

## Warstwa danych

| Encja | Najważniejsze pola | Uwagi |
| --- | --- | --- |
| `User` | `email`, `password_hash`, `role`, `created_at` | Role: `user`, `admin`; hasła w bcrypt |
| `Device` | `name`, `owner_id`, `status`, `secret_hash`, `token_version`, `last_reading_at` | `token_version` unieważnia tokeny przy rotacji sekretu |
| `RefreshToken` | `token_jti`, `token_hash`, `expires_at`, `revoked` | Jeden aktywny token per użytkownik, przechowywany jako skrót |
| `Reading` | `device_id`, `payload`, `payload_size`, `device_timestamp`, `received_at` | Wymuszenie limitu rozmiaru i częstotliwości |
| `SecurityEvent` | `actor_type`, `actor_id`, `event_type`, `status`, `detail` | Dostępne dla administratora, źródło audytu |

SQLite został wybrany ze względu na prosty start i przenośność – w kodzie brak elementów uzależniających od konkretnego dialektu, więc migracja do Postgresa ogranicza się do zmiany `DATABASE_URL`.

## Kluczowe przepływy

1. **Onboarding użytkownika**  
   Rejestracja (`/auth/register`) → Logowanie (`/auth/login`) → Odbiór tokenów → (opcjonalnie) odświeżanie (`/auth/refresh`) → Wylogowanie (`/auth/logout`).

2. **Provisioning urządzenia**  
   Użytkownik tworzy urządzenie (`/devices`) → otrzymuje jednorazowy sekret → przenosi dane do urządzenia.

3. **Uwierzytelnienie urządzenia**  
   Urządzenie wymienia `device_id + secret` na token (`/device/token`) → token zawiera `token_version`, dzięki czemu rotacja sekretu natychmiast unieważnia stare tokeny.

4. **Wysyłka danych**  
   Urządzenie wysyła odczyty (`/device/readings`) → system kontroluje limity (rozmiar, częstość) i zapisuje metadane (`received_at`, `payload_size`).

5. **Odczyt danych przez właściciela**  
   Użytkownik filtruje odczyty (`/devices/{id}/readings`) lub pobiera metadane (`/devices/{id}/readings/meta`). Administrator widzi wszystkie urządzenia.

6. **Incydent bezpieczeństwa**  
   Użytkownik blokuje urządzenie (`/devices/{id}/deactivate`) lub rotuje sekret (`/devices/{id}/rotate-secret`). W obu przypadkach tokeny stają się nieważne.

## Zabezpieczenia i dobre praktyki

- **Oddzielne klucze JWT** dla ludzi (`jwt_secret_key`, `jwt_refresh_secret_key`) i urządzeń (`jwt_device_secret_key`), co uniemożliwia użycie niewłaściwego tokenu na innym kanale.
- **Krótki TTL** tokenów dostępnych (domyślnie 15 min dla użytkownika, 5 min dla urządzenia), możliwość odświeżenia tylko z ważnym tokenem długoterminowym zapisanym w bazie.
- **Hashowanie** haseł oraz sekretów urządzeń przy użyciu `passlib[bcrypt]`.
- **Rate limiting** – sprawdzanie `last_reading_at` zapobiega zalewaniu endpointu przez urządzenie.
- **Rozmiar payloadu** weryfikowany przed zapisem – brak nielimitowanych struktur JSON.
- **Logi zdarzeń** – każdy sukces/odmowa zapisywany w `SecurityEvent` (widok administracyjny `/admin/security-events`).
- **Krótka treść błędów** – komunikaty w języku polskim, ale bez zdradzania szczegółów implementacyjnych.
- **Domyślny administrator** tworzony przy starcie – można zmienić dane w `.env`.

## Scenariusze awaryjne i rozszerzenia

- W przypadku utraty sekretu urządzenia właściciel może natychmiast rotować sekret lub zablokować urządzenie. Tokeny przestaną działać dzięki inkrementacji `token_version`.
- W przypadku kradzieży refresh tokenu – wystarczy wylogować się (`/auth/logout`), co unieważni wpis w tabeli `refresh_tokens`.
- Logi pozwalają odtworzyć próby włamania (np. zły sekret lub obce urządzenie).

### Możliwe usprawnienia

- Podłączenie zewnętrznego systemu kolejkowego (np. RabbitMQ) do akwizycji odczytów i asynchronicznej obróbki.
- Dodanie WebSocketów lub SSE dla podglądu na żywo, bazujących na tych samych serwisach i autoryzacji.
- Wprowadzenie mechanizmu polityk (np. odcięcie urządzenia po N odmowach).
- Wsparcie dla podpisów HMAC w odczytach (podwójne zabezpieczenie poza JWT).
- Rozszerzenie panelu PyQt o widoki analityczne (wykresy) oraz konfigurację limitów po stronie użytkownika.
