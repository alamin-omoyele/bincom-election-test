from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import os
from urllib.parse import parse_qs, urlparse
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def _require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


DB_CONFIG = {
    "host": _require_env("DB_HOST"),
    "port": int(_require_env("DB_PORT")),
    "user": _require_env("DB_USER"),
    "password": _require_env("DB_PASSWORD"),
    "database": _require_env("DB_NAME"),
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def layout(title, body_html):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} - Bincom Election Test</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; padding: 0 15px; background: #f8f9fa; color: #222; }}
        nav {{ background: #1b4332; padding: 12px 18px; border-radius: 6px; margin-bottom: 24px; }}
        nav a {{ color: #fff; text-decoration: none; margin-right: 20px; font-weight: bold; }}
        nav a:hover {{ text-decoration: underline; }}
        .card {{ background: #fff; padding: 20px; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        label {{ display: block; font-weight: bold; margin-top: 12px; }}
        select, input[type="text"], input[type="number"] {{ width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
        button {{ background: #2d6a4f; color: white; border: none; padding: 10px 18px; border-radius: 4px; cursor: pointer; margin-top: 16px; font-size: 15px; }}
        button:hover {{ background: #1b4332; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #e9ecef; }}
        .alert {{ padding: 12px; background: #d8f3dc; border-left: 4px solid #2d6a4f; margin-bottom: 16px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }}
    </style>
</head>
<body>
    <nav>
        <a href="/q1">Q1: Polling Unit Result</a>
        <a href="/q2">Q2: LGA Summed Results</a>
        <a href="/q3">Q3: Add New Polling Unit</a>
    </nav>
    {body_html}
</body>
</html>"""


class ElectionHandler(BaseHTTPRequestHandler):

    def send_html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/wards":
            lga_id = params.get("lga_id", [""])[0]
            conn = get_db()
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT w.uniqueid, w.ward_id, w.ward_name,
                       (SELECT COUNT(DISTINCT pu.uniqueid)
                        FROM polling_unit pu
                        WHERE pu.uniquewardid = w.uniqueid
                           OR (pu.ward_id = w.ward_id AND pu.lga_id = w.lga_id)
                       ) AS pu_count
                FROM ward w
                WHERE w.lga_id = %s
                ORDER BY w.ward_name
                """,
                (lga_id,),
            )
            rows = cur.fetchall()
            conn.close()
            return self.send_json(rows)

        if path == "/api/polling-units":
            ward_uniqueid = params.get("ward_uniqueid", [""])[0]
            conn = get_db()
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT DISTINCT pu.uniqueid, pu.polling_unit_number, pu.polling_unit_name
                FROM polling_unit pu
                LEFT JOIN ward w ON w.uniqueid = %s
                WHERE pu.uniquewardid = %s
                   OR (pu.ward_id = w.ward_id AND pu.lga_id = w.lga_id)
                ORDER BY pu.uniqueid
                """,
                (ward_uniqueid, ward_uniqueid),
            )
            rows = cur.fetchall()
            conn.close()
            return self.send_json(rows)

        if path in ("/", "/q1"):
            return self.render_q1(params)
        if path == "/q2":
            return self.render_q2(params)
        if path == "/q3":
            return self.render_q3(params)

        self.send_html(
            layout("Not Found", "<div class='card'><h2>404 Page Not Found</h2></div>"),
            404,
        )

    def do_POST(self):
        if self.path == "/q3":
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(raw_body)
            return self.handle_q3_submit(form)
        self.send_html(
            layout("Method Not Allowed", "<div class='card'><h2>405</h2></div>"), 405
        )

    def render_q1(self, params):
        pu_uniqueid = params.get("pu_id", [""])[0]
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT l.lga_id, l.lga_name, COUNT(pu.uniqueid) AS pu_count
            FROM lga l
            LEFT JOIN polling_unit pu ON pu.lga_id = l.lga_id
            WHERE l.state_id = 25
            GROUP BY l.lga_id, l.lga_name
            ORDER BY l.lga_name
            """
        )
        lgas = cur.fetchall()
        lga_options = "".join(
            f"<option value='{r['lga_id']}'>{html.escape(r['lga_name'])} ({r['pu_count']} PUs)</option>"
            for r in lgas
        )

        result_html = ""
        if pu_uniqueid:
            cur.execute(
                """
                SELECT pu.uniqueid, pu.polling_unit_number, pu.polling_unit_name,
                       w.ward_name, l.lga_name
                FROM polling_unit pu
                LEFT JOIN ward w ON (pu.uniquewardid = w.uniqueid OR (pu.ward_id = w.ward_id AND pu.lga_id = w.lga_id))
                LEFT JOIN lga l ON pu.lga_id = l.lga_id
                WHERE pu.uniqueid = %s
                LIMIT 1
                """,
                (pu_uniqueid,),
            )
            pu_info = cur.fetchone()

            cur.execute(
                """
                SELECT party_abbreviation, party_score, entered_by_user, date_entered
                FROM announced_pu_results
                WHERE polling_unit_uniqueid = %s
                ORDER BY party_abbreviation
                """,
                (pu_uniqueid,),
            )
            scores = cur.fetchall()

            if pu_info:
                rows_html = (
                    "".join(
                        f"<tr><td>{html.escape(s['party_abbreviation'])}</td>"
                        f"<td><strong>{s['party_score']}</strong></td>"
                        f"<td>{html.escape(str(s['entered_by_user'] or ''))}</td></tr>"
                        for s in scores
                    )
                    or "<tr><td colspan='3'>No announced results found for this"
                    " polling unit.</td></tr>"
                )

                result_html = f"""
                <div class="card">
                    <h3>{html.escape(pu_info['polling_unit_name'] or 'Unnamed PU')} ({html.escape(pu_info['polling_unit_number'] or '')})</h3>
                    <p><strong>Unique ID:</strong> {pu_info['uniqueid']} | <strong>Ward:</strong> {html.escape(str(pu_info['ward_name'] or 'N/A'))} | <strong>LGA:</strong> {html.escape(str(pu_info['lga_name'] or 'N/A'))}</p>
                    <table>
                        <thead><tr><th>Party</th><th>Score</th><th>Entered By</th></tr></thead>
                        <tbody>{rows_html}</tbody>
                    </table>
                </div>"""
        conn.close()

        body = f"""
        <div class="card">
            <h2>Question 1: Individual Polling Unit Result (Delta State)</h2>
            <form method="GET" action="/q1">
                <label for="lga">1. Select Local Government (LGA):</label>
                <select id="lga" onchange="loadWards(this.value)">
                    <option value="">-- Choose LGA --</option>
                    {lga_options}
                </select>

                <label for="ward">2. Select Ward:</label>
                <select id="ward" onchange="loadPUs(this.value)" disabled>
                    <option value="">-- Choose LGA first --</option>
                </select>

                <label for="pu_id">3. Select Polling Unit:</label>
                <select id="pu_id" name="pu_id" required disabled>
                    <option value="">-- Choose Ward first --</option>
                </select>

                <button type="submit">View Polling Unit Result</button>
            </form>
        </div>
        {result_html}
        <script>
            async function loadWards(lgaId) {{
                const wardSelect = document.getElementById('ward');
                const puSelect = document.getElementById('pu_id');
                wardSelect.innerHTML = '<option value="">Loading...</option>';
                puSelect.innerHTML = '<option value="">-- Choose Ward first --</option>';
                puSelect.disabled = true;
                if (!lgaId) {{ wardSelect.disabled = true; return; }}

                const res = await fetch('/api/wards?lga_id=' + encodeURIComponent(lgaId));
                const wards = await res.json();
                wardSelect.innerHTML = '<option value="">-- Choose Ward --</option>' +
                    wards.map(w => `<option value="${{w.uniqueid}}">${{w.ward_name}} (${{w.pu_count}} PUs)</option>`).join('');
                wardSelect.disabled = false;
            }}

            async function loadPUs(wardUniqueId) {{
                const puSelect = document.getElementById('pu_id');
                puSelect.innerHTML = '<option value="">Loading...</option>';
                if (!wardUniqueId) {{ puSelect.disabled = true; return; }}

                const res = await fetch('/api/polling-units?ward_uniqueid=' + encodeURIComponent(wardUniqueId));
                const pus = await res.json();
                if (pus.length === 0) {{
                    puSelect.innerHTML = '<option value="">-- No polling units recorded in this ward --</option>';
                    puSelect.disabled = true;
                    return;
                }}
                puSelect.innerHTML = '<option value="">-- Choose Polling Unit --</option>' +
                    pus.map(p => `<option value="${{p.uniqueid}}">[ID ${{p.uniqueid}}] ${{p.polling_unit_name || 'Unnamed'}} (${{p.polling_unit_number || ''}})</option>`).join('');
                puSelect.disabled = false;
            }}
        </script>
        """
        self.send_html(layout("Polling Unit Result", body))

    def render_q2(self, params):
        selected_lga = params.get("lga_id", [""])[0]
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT l.lga_id, l.lga_name, COUNT(r.result_id) AS result_rows
            FROM lga l
            LEFT JOIN polling_unit pu ON pu.lga_id = l.lga_id
            LEFT JOIN announced_pu_results r ON r.polling_unit_uniqueid = pu.uniqueid
            WHERE l.state_id = 25
            GROUP BY l.lga_id, l.lga_name
            ORDER BY l.lga_name
            """
        )
        lgas = cur.fetchall()
        lga_options = "".join(
            f"<option value='{r['lga_id']}' {'selected' if str(r['lga_id']) == selected_lga else ''}>"
            f"{html.escape(r['lga_name'])} ({r['result_rows']} PU results)</option>"
            for r in lgas
        )

        summary_html = ""
        if selected_lga:
            cur.execute(
                """
                SELECT TRIM(r.party_abbreviation) AS party, SUM(r.party_score) AS total_score
                FROM announced_pu_results r
                INNER JOIN polling_unit pu ON r.polling_unit_uniqueid = pu.uniqueid
                WHERE pu.lga_id = %s
                GROUP BY TRIM(r.party_abbreviation)
                ORDER BY party
                """,
                (selected_lga,),
            )
            summed_map = {
                row["party"]: int(row["total_score"]) for row in cur.fetchall()
            }

            cur.execute(
                """
                SELECT TRIM(r.party_abbreviation) AS party, r.party_score
                FROM announced_lga_results r
                INNER JOIN lga l ON l.lga_name = r.lga_name
                WHERE l.lga_id = %s
                ORDER BY party
                """,
                (selected_lga,),
            )
            announced_map = {
                row["party"]: int(row["party_score"]) for row in cur.fetchall()
            }

            all_parties = sorted(set(summed_map.keys()) | set(announced_map.keys()))

            if all_parties:
                tr_list = []
                for party in all_parties:
                    calc_total = summed_map.get(party, 0)
                    official_lga = announced_map.get(party)
                    official_str = (
                        f"{official_lga:,}" if official_lga is not None else "N/A"
                    )
                    tr_list.append(
                        f"<tr><td>{html.escape(party)}</td><td><strong>{calc_total:,}</strong></td><td>{official_str}</td></tr>"
                    )
                rows_html = "".join(tr_list)
            else:
                rows_html = (
                    "<tr><td colspan='3'>No polling unit or LGA results recorded for"
                    " this LGA.</td></tr>"
                )

            summary_html = f"""
            <div class="card">
                <h3>Summed Polling Unit Results for Selected LGA</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Party</th>
                            <th>Summed PU Total (Calculated)</th>
                            <th>Announced LGA Result (Comparison Only)</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>"""
        conn.close()

        body = f"""
        <div class="card">
            <h2>Question 2: LGA Summed Polling Unit Results</h2>
            <form method="GET" action="/q2">
                <label for="lga_id">Select Local Government Area:</label>
                <select id="lga_id" name="lga_id" required>
                    <option value="">-- Choose LGA --</option>
                    {lga_options}
                </select>
                <button type="submit">Calculate LGA Total</button>
            </form>
        </div>
        {summary_html}
        """
        self.send_html(layout("LGA Summed Results", body))

    def get_parties(self, cur):
        try:
            cur.execute("SELECT partyname FROM party ORDER BY partyname")
            rows = [
                r["partyname"].strip() for r in cur.fetchall() if r.get("partyname")
            ]
            if rows:
                return rows
        except mysql.connector.Error:
            pass
        cur.execute(
            "SELECT DISTINCT TRIM(party_abbreviation) AS party FROM"
            " announced_lga_results ORDER BY party"
        )
        rows = [r["party"] for r in cur.fetchall() if r.get("party")]
        return rows or [
            "PDP",
            "DPP",
            "ACN",
            "PPA",
            "CDC",
            "JP",
            "ANPP",
            "LABO",
            "CPP",
        ]

    def render_q3(self, params):
        success_msg = ""
        if params.get("saved") == ["1"]:
            new_id = html.escape(params.get("new_id", [""])[0])
            success_msg = (
                "<div class='alert'>New polling unit (Unique ID:"
                f" <strong>{new_id}</strong>) and all party results saved"
                " successfully!</div>"
            )

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT lga_id, lga_name FROM lga WHERE state_id = 25 ORDER BY lga_name"
        )
        lgas = cur.fetchall()
        lga_options = "".join(
            f"<option value='{r['lga_id']}'>{html.escape(r['lga_name'])}</option>"
            for r in lgas
        )

        parties = self.get_parties(cur)
        conn.close()

        party_inputs = "".join(
            f"<div><label>{html.escape(p)}</label>"
            f"<input type='number' name='score_{html.escape(p)}' min='0' value='0' required></div>"
            for p in parties
        )

        body = f"""
        {success_msg}
        <div class="card">
            <h2>Question 3: Add New Polling Unit & All Party Results</h2>
            <form method="POST" action="/q3">
                <label for="lga_id">1. Select LGA (Delta State):</label>
                <select id="lga_id" name="lga_id" onchange="loadWards(this.value)" required>
                    <option value="">-- Choose LGA --</option>
                    {lga_options}
                </select>

                <label for="ward_uniqueid">2. Select Ward:</label>
                <select id="ward_uniqueid" name="ward_uniqueid" required disabled>
                    <option value="">-- Choose LGA first --</option>
                </select>

                <label for="pu_number">Polling Unit Number (e.g., DT1901001):</label>
                <input type="text" id="pu_number" name="pu_number" required>

                <label for="pu_name">Polling Unit Name:</label>
                <input type="text" id="pu_name" name="pu_name" required>

                <label for="pu_desc">Polling Unit Description:</label>
                <input type="text" id="pu_desc" name="pu_desc" placeholder="Optional description">

                <label for="entered_by">Entered By (Your Name):</label>
                <input type="text" id="entered_by" name="entered_by" required>

                <h3>Party Scores</h3>
                <div class="grid">
                    {party_inputs}
                </div>

                <button type="submit">Save Polling Unit & Results</button>
            </form>
        </div>
        <script>
            async function loadWards(lgaId) {{
                const wardSelect = document.getElementById('ward_uniqueid');
                wardSelect.innerHTML = '<option value="">Loading...</option>';
                if (!lgaId) {{ wardSelect.disabled = true; return; }}

                const res = await fetch('/api/wards?lga_id=' + encodeURIComponent(lgaId));
                const wards = await res.json();
                wardSelect.innerHTML = '<option value="">-- Choose Ward --</option>' +
                    wards.map(w => `<option value="${{w.uniqueid}}">${{w.ward_name}} (${{w.pu_count}} PUs)</option>`).join('');
                wardSelect.disabled = false;
            }}
        </script>
        """
        self.send_html(layout("Add Polling Unit Result", body))

    def handle_q3_submit(self, form):
        lga_id = form.get("lga_id", [""])[0]
        ward_uniqueid = form.get("ward_uniqueid", [""])[0]
        pu_number = form.get("pu_number", [""])[0].strip()
        pu_name = form.get("pu_name", [""])[0].strip()
        pu_desc = form.get("pu_desc", [""])[0].strip()
        entered_by = form.get("entered_by", ["Admin"])[0].strip()
        user_ip = self.client_address[0]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT ward_id FROM ward WHERE uniqueid = %s", (ward_uniqueid,)
        )
        ward_row = cur.fetchone()
        ward_id = ward_row["ward_id"] if ward_row else 0

        cur.execute(
            "SELECT COALESCE(MAX(polling_unit_id), 0) + 1 AS next_id FROM"
            " polling_unit WHERE uniquewardid = %s",
            (ward_uniqueid,),
        )
        next_pu_id = cur.fetchone()["next_id"]

        cur.execute(
            """
            INSERT INTO polling_unit (
                polling_unit_id, ward_id, lga_id, uniquewardid,
                polling_unit_number, polling_unit_name, polling_unit_description,
                entered_by_user, date_entered, user_ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                next_pu_id,
                ward_id,
                lga_id,
                ward_uniqueid,
                pu_number,
                pu_name,
                pu_desc,
                entered_by,
                now_str,
                user_ip,
            ),
        )
        new_pu_uniqueid = cur.lastrowid

        parties = self.get_parties(cur)

        for party in parties:
            raw_score = form.get(f"score_{party}", ["0"])[0]
            score = int(raw_score) if raw_score.isdigit() else 0
            party_abbr = party[:4]
            cur.execute(
                """
                INSERT INTO announced_pu_results (
                    polling_unit_uniqueid, party_abbreviation, party_score,
                    entered_by_user, date_entered, user_ip_address
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(new_pu_uniqueid),
                    party_abbr,
                    score,
                    entered_by,
                    now_str,
                    user_ip,
                ),
            )

        conn.commit()
        conn.close()

        self.send_response(303)
        self.send_header("Location", f"/q3?saved=1&new_id={new_pu_uniqueid}")
        self.end_headers()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), ElectionHandler)
    print(f"Server running on http://localhost:{port}")
    server.serve_forever()