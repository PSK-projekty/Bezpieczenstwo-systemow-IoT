# Dokumentacja API

Wszystkie odpowiedzi i komunikaty zwracane są w języku polskim. Domyślna ścieżka bazowa: `http://127.0.0.1:8000`.

## Autoryzacja ludzi (`/auth`)

| Metoda | Ścieżka | Opis |
| --- | --- | --- |
| `POST` | `/auth/register` | Rejestracja nowego użytkownika (`email`, `password`). |
| `POST` | `/auth/login` | Logowanie; zwraca token dostępowy (`bearer`) i odświeżający. |
| `POST` | `/auth/refresh` | Odświeża token dostępowy na podstawie refresh tokenu. |
| `POST` | `/auth/logout` | Unieważnia refresh token (wymaga nagłówka `Authorization: Bearer <access_token>`). |

### Przykład logowania

```http
POST /auth/login
Content-Type: application/json

{
  "email": "jan@example.com",
  "password": "SilneHaslo1!"
}
```

Odpowiedź:

```json
{
  "access_token": "<jwt-access>",
  "refresh_token": "<jwt-refresh>",
  "token_type": "bearer",
  "expires_in_minutes": 15
}
```

Authorization header dla dalszych zapytań ludzi: `Authorization: Bearer <access_token>`.

## Użytkownicy i urządzenia (`/devices`)

| Metoda | Ścieżka | Opis | Dostęp |
| --- | --- | --- | --- |
| `POST` | `/devices` | Tworzy urządzenie, zwraca `device_id` i jednorazowy `device_secret`. | właściciel |
| `GET` | `/devices` | Lista urządzeń użytkownika (administrator widzi wszystkie). | user/admin |
| `GET` | `/devices/{device_id}` | Szczegóły urządzenia. | właściciel / admin |
| `POST` | `/devices/{device_id}/deactivate` | Blokuje urządzenie i unieważnia tokeny. | właściciel / admin |
| `DELETE` | `/devices/{device_id}` | Logiczne usunięcie (status `deleted`). | właściciel / admin |
| `POST` | `/devices/{device_id}/rotate-secret` | Generuje nowy sekret, unieważnia stare tokeny. | właściciel / admin |
| `POST` | `/devices/{device_id}/invalidate-tokens` | Natychmiast unieważnia tokeny (bez zmiany sekretu). | właściciel / admin |
| `GET` | `/devices/{device_id}/readings` | Lista odczytów (parametry `limit`, `since`, `until`). | właściciel / admin |
| `GET` | `/devices/{device_id}/readings/meta` | Metadane (`total_readings`, najnowszy/najstarszy czas). | właściciel / admin |

### Przykład tworzenia urządzenia

```http
POST /devices
Authorization: Bearer <user-access-token>
Content-Type: application/json

{ "name": "Czujnik 01" }
```

Odpowiedź:

```json
{
  "device_id": "a1b2c3d4-...",
  "device_secret": "długislots123..."
}
```

Sekret pojawia się tylko raz – należy zapisać go po stronie użytkownika i wprowadzić w urządzeniu.

## Interfejs urządzenia (`/device`)

| Metoda | Ścieżka | Opis | Nagłówek |
| --- | --- | --- | --- |
| `POST` | `/device/token` | Wymiana `device_id + device_secret` na krótki token urządzenia. | brak |
| `POST` | `/device/readings` | Przekazanie odczytu (`payload` – dowolny JSON, `device_timestamp` opcjonalnie). | `Authorization: Bearer <device-token>` |

### Przykład przesyłania odczytu

```http
POST /device/readings
Authorization: Bearer <device-access-token>
Content-Type: application/json

{
  "device_timestamp": "2025-02-10T14:20:00Z",
  "payload": {
    "temperature": 21.5,
    "humidity": 40
  }
}
```

Odpowiedź:

```json
{
  "id": 12,
  "device_id": "a1b2c3d4-...",
  "device_timestamp": "2025-02-10T14:20:00+00:00",
  "received_at": "2025-02-10T14:20:05.234512+00:00",
  "payload": {
    "temperature": 21.5,
    "humidity": 40
  },
  "payload_size": 54
}
```

Limit rozmiaru ładunku: `DATA_PAYLOAD_LIMIT_BYTES` (domyślnie 2048 bajtów). Limit częstości: `MIN_SECONDS_BETWEEN_READINGS` (domyślnie 1 s).

## Administracja (`/admin`)

| Metoda | Ścieżka | Opis | Dostęp |
| --- | --- | --- | --- |
| `GET` | `/admin/security-events` | Maks. 500 ostatnich zdarzeń bezpieczeństwa (`limit` domyślnie 100). | administrator |

Struktura wpisu:

```json
{
  "id": 5,
  "created_at": "2025-02-10T12:00:10+00:00",
  "actor_type": "device",
  "actor_id": "a1b2c3d4-...",
  "event_type": "reading_rate_limit",
  "status": "denied",
  "detail": "Przekroczony limit częstości."
}
```

## Punkt zdrowia

- `GET /healthz` – dostępny publicznie, zwraca nazwę aplikacji, środowisko i aktualny czas w UTC.

## Kody odpowiedzi

| Kod | Znaczenie |
| --- | --- |
| `200 OK` | Operacja poprawna. |
| `201 Created` | Utworzenie zasobu (rejestracja, odczyt, urządzenie). |
| `204 No Content` | Wylogowanie / brak treści w odpowiedzi. |
| `400 Bad Request` | Błąd walidacji danych (np. zbyt krótkie hasło, brak pola). |
| `401 Unauthorized` | Brak tokenu lub zły token. |
| `403 Forbidden` | Brak uprawnień (np. cudze urządzenie). |
| `404 Not Found` | Zasób nie istnieje. |
| `413 Payload Too Large` | Ładunek odczytu przekracza limit. |
| `429 Too Many Requests` | Przekroczony limit częstości urządzenia. |

## Sekwencja przykładowa (skrót)

1. `POST /auth/register` → utworzenie konta.
2. `POST /auth/login` → tokeny użytkownika.
3. `POST /devices` → `device_id`, `device_secret`.
4. `POST /device/token` → token urządzenia.
5. `POST /device/readings` → zapis odczytu.
6. `GET /devices/{id}/readings` → odczyt danych przez właściciela.
7. `POST /devices/{id}/rotate-secret` → rotacja w razie incydentu.

Każde z powyższych wywołań jest objęte walidacją oraz logowane w `security_events` (status `success`, `denied` lub `error`).
