# BasilCare API

Jakarta EE 11 REST API deployed as `api.war` on WildFly.

## Endpoints

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | Public | Service liveness |
| `GET` | `/api/me` | Farmer, Admin | Current authenticated user |
| `GET` | `/api/devices` | Farmer, Admin | List registered IoT gateways |
| `GET` | `/api/devices/{deviceId}` | Farmer, Admin | Read one gateway |
| `POST` | `/api/devices` | Admin | Register a gateway |
| `PUT` | `/api/devices/{deviceId}` | Admin | Update gateway metadata or availability |
| `DELETE` | `/api/devices/{deviceId}` | Admin | Remove a gateway |

Protected endpoints require `Authorization: Bearer <access-token>` with a token issued by the
BasilCare IAM.

## Device representation

```json
{
  "deviceId": "basil-pi-01",
  "name": "Greenhouse Raspberry Pi",
  "location": "SUP'COM Lab",
  "enabled": true,
  "createdAt": "2026-11-09T17:00:00+01:00",
  "updatedAt": "2026-11-09T17:00:00+01:00"
}
```

Create a device with an Admin token:

```bash
curl -i -X POST http://localhost:8080/api/devices \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"basil-pi-01","name":"Greenhouse Raspberry Pi","location":"SUPCOM Lab"}'
```

Device IDs contain 3 to 32 lowercase letters, digits or hyphens. Names contain 3 to 80
characters and locations contain at most 120 characters.

## Build and test

Requires JDK 25 and Maven 3.9+:

```bash
mvn clean verify
```
