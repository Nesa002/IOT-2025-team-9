import os

from flask import Flask, jsonify, render_template
from influxdb_client import InfluxDBClient

from settings import load_settings


def create_app(settings_path=None):
    settings = load_settings(settings_path or "settings.json")
    influx_settings = settings.get("influxdb", {})
    grafana_url = settings.get("grafana", {}).get("url", "http://localhost:3000")
    dashboard_uid = settings.get("grafana", {}).get("dashboard_uid", "")

    app = Flask(__name__)

    influx_client = InfluxDBClient(
        url=os.getenv("INFLUX_URL", influx_settings.get("url")),
        token=os.getenv("INFLUX_TOKEN", influx_settings.get("token")),
        org=os.getenv("INFLUX_ORG", influx_settings.get("org")),
    )

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            grafana_url=grafana_url,
            dashboard_uid=dashboard_uid,
        )

    @app.route("/api/states")
    def states():
        query_api = influx_client.query_api()
        query = f'''
        from(bucket: "{influx_settings.get("bucket")}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._field == "value" or r._field == "state")
          |> group(columns: ["sensor", "_field"])
          |> last()
        '''

        try:
            tables = query_api.query(query=query, org=os.getenv("INFLUX_ORG", influx_settings.get("org")))
        except Exception:
            return jsonify({"states": [], "warning": "InfluxDB nije dostupan."}), 503

        latest = {}
        for table in tables:
            for record in table.records:
                sensor = record.values.get("sensor", "unknown")
                entry = latest.setdefault(
                    sensor,
                    {
                        "sensor": sensor,
                        "sensor_type": record.get_measurement(),
                        "device": record.values.get("device", "unknown"),
                        "pi_id": record.values.get("pi_id", "unknown"),
                        "unit": record.values.get("unit"),
                        "timestamp": record.get_time().isoformat() if record.get_time() else None,
                    },
                )
                if record.get_field() == "value":
                    entry["value"] = record.get_value()
                if record.get_field() == "state":
                    entry["state"] = record.get_value()

        return jsonify({"states": sorted(latest.values(), key=lambda item: item["sensor"])})


    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5001)
