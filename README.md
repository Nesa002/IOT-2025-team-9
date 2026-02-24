# IOT-2025-team-9

## Arhitektura

Projekat sada sadrži kompletan tok za prijem podataka sa Raspberry Pi uređaja, skladištenje u InfluxDB i vizuelizaciju u Grafani, uz korisničku web aplikaciju:

1. **PI uređaji / simulatori** šalju MQTT poruke ka brokeru Mosquitto.
2. **`mqtt_influx_server.py`** prima MQTT poruke i upisuje očitavanja u InfluxDB.
3. **Grafana** koristi InfluxDB kao data source za dashboard prikaz istorije podataka.
4. **`web_app.py`** prikazuje trenutno stanje svakog senzora/elementa i ugrađeni Grafana panel.

## Pokretanje sistema

> Potrebni alati: Docker + Docker Compose.

```bash
docker compose up -d
```

Servisi:
- Mosquitto: `localhost:1883`
- InfluxDB: `http://localhost:8086`
- Grafana: `http://localhost:3000` (admin/admin123)
- Korisnička web aplikacija: `http://localhost:5001`

## Konfiguracija

Konfiguracija je u `settings.json`:

- `mqtt` – host/port brokera i teme.
- `influxdb` – URL, token, organizacija i bucket.
- `grafana.url` – URL Grafana instance.
- `grafana.dashboard_uid` – UID dashboard-a za prikaz u web aplikaciji.

Ako `grafana.dashboard_uid` nije podešen, web aplikacija će i dalje prikazivati trenutno stanje elemenata sistema, ali bez ugrađenog panela.

## MQTT → Influx server

Server aplikacija (`mqtt_influx_server.py`) radi sledeće:
- subscribuje se na podrazumevanu temu i sve teme definisane u konfiguraciji,
- parsira JSON payload sa listom `readings`,
- transformiše očitavanja u InfluxDB point-ove,
- upisuje podatke asinhrono u InfluxDB bucket.

Health endpoint:

```bash
curl http://localhost:5000/health
```

## Korisnička web aplikacija

Web aplikacija (`web_app.py`) obezbeđuje:
- **`/`**: stranicu sa tabelom trenutnog stanja svih senzora/elemenata,
- **`/api/states`**: JSON API za poslednje poznato stanje po senzoru,
- ugrađen Grafana panel preko `iframe` (kada je podešen dashboard UID).

Stranica automatski osvežava stanje na svakih 10 sekundi.
