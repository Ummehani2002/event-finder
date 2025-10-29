from flask import Flask, request, render_template_string, redirect, url_for
import requests
from datetime import datetime
import pytz
import sqlite3

app = Flask(__name__)

# ==============================
# 🔑 API KEYS (Replace with your own)
# ==============================
PREDICTHQ_TOKEN = "z2U_46IOcimtq8GuHMuzRWp0dJe4fKKtms-acObz"
TICKETMASTER_KEY = "6cXVG6fHpIPTcgukSSZaPwrWAQWbEGs9"
EVENTBRITE_TOKEN = "DJS2WBMYZZIC2OLUZB"

DB_FILE = 'events.db'

# ==============================
# 🔹 Database helper
# ==============================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS event_registrations (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_email TEXT,
                 event_name TEXT,
                 event_date TEXT,
                 source TEXT)''')
    conn.commit()
    conn.close()

def register_user(email, event_name, event_date, source):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO event_registrations (user_email, event_name, event_date, source) VALUES (?, ?, ?, ?)",
              (email, event_name, event_date, source))
    conn.commit()
    conn.close()

def count_registrations(event_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM event_registrations WHERE LOWER(TRIM(event_name)) = ?", (event_name.lower().strip(),))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_registered_users(event_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_email FROM event_registrations WHERE LOWER(TRIM(event_name)) = ?", (event_name.lower().strip(),))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# ==============================
# 🔹 Fetch Events
# ==============================
def fetch_predicthq_events(city, from_date, to_date):
    url = "https://api.predicthq.com/v1/events/"
    headers = {"Authorization": f"Bearer {PREDICTHQ_TOKEN}"}
    params = {"q": city, "active.gte": from_date, "active.lte": to_date, "limit": 30, "sort": "start"}
    events = []
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        print("PredictHQ response:", data)
        for e in data.get("results", []):
            events.append({
                "name": e.get("title", "N/A"),
                "venue": e.get("entities", [{}])[0].get("name", "N/A") if e.get("entities") else "N/A",
                "date": e.get("start", "N/A"),
                "source": "PredictHQ"
            })
    except Exception as ex:
        print("PredictHQ error:", ex)
    return events

def fetch_ticketmaster_events(city, from_date, to_date):
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TICKETMASTER_KEY,
        "city": city,
        "startDateTime": from_date + "T00:00:00Z",
        "endDateTime": to_date + "T23:59:59Z",
        "size": 30
    }
    events = []
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        print("Ticketmaster response:", data)
        for e in data.get("_embedded", {}).get("events", []):
            events.append({
                "name": e.get("name", "N/A"),
                "venue": e["_embedded"]["venues"][0]["name"] if "_embedded" in e else "N/A",
                "date": e.get("dates", {}).get("start", {}).get("dateTime", "N/A"),
                "source": "Ticketmaster"
            })
    except Exception as ex:
        print("Ticketmaster error:", ex)
    return events

def fetch_eventbrite_events(city, from_date, to_date):
    url = "https://www.eventbriteapi.com/v3/events/search/"
    headers = {"Authorization": f"Bearer {EVENTBRITE_TOKEN}"}
    params = {
        "q": city,
        "start_date.range_start": from_date + "T00:00:00Z",
        "start_date.range_end": to_date + "T23:59:59Z",
        "expand": "venue"
    }
    events = []
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        print("Eventbrite response:", data)
        for e in data.get("events", []):
            events.append({
                "name": e.get("name", {}).get("text", "N/A"),
                "venue": e.get("venue", {}).get("name", "N/A"),
                "date": e.get("start", {}).get("local", "N/A"),
                "source": "Eventbrite"
            })
    except Exception as ex:
        print("Eventbrite error:", ex)
    return events

# ==============================
# 🔹 UTC to Local
# ==============================
def convert_utc_to_local(utc_str, tz_str):
    if utc_str == "N/A" or not utc_str:
        return "N/A"
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        local_tz = pytz.timezone(tz_str)
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime("%Y-%m-%d %H:%M")
    except:
        return utc_str

# ==============================
# 🔹 Flask Routes
# ==============================
@app.route('/', methods=['GET', 'POST'])
def home():
    init_db()
    events = []
    city = from_date = to_date = ""
    if request.method == 'POST':
        city = request.form.get('city')
        from_date = request.form.get('from_date')
        to_date = request.form.get('to_date')
        if city and from_date and to_date:
            all_events = []
            all_events.extend(fetch_predicthq_events(city, from_date, to_date))
            all_events.extend(fetch_ticketmaster_events(city, from_date, to_date))
            all_events.extend(fetch_eventbrite_events(city, from_date, to_date))
            
            # Remove duplicates
            seen = set()
            for e in all_events:
                key = (e['name'].lower(), e['date'])
                if key not in seen:
                    seen.add(key)
                    events.append(e)

            # Convert dates and add registration info
            timezone_map = {
                'Dubai': 'Asia/Dubai',
                'London': 'Europe/London',
                'New York': 'America/New_York',
                'Mumbai': 'Asia/Kolkata',
                'Delhi': 'Asia/Kolkata',
            }
            tz_str = timezone_map.get(city, 'UTC')
            for e in events:
                e['date'] = convert_utc_to_local(e['date'], tz_str)
                e['registrations'] = count_registrations(e['name'])
                e['registered_users'] = get_registered_users(e['name'])

    html = """
    <h2>🌍 Global Event Finder</h2>
    <form method="POST">
        City: <input type="text" name="city" value="{{ city }}" required>
        From: <input type="date" name="from_date" value="{{ from_date }}" required>
        To: <input type="date" name="to_date" value="{{ to_date }}" required>
        <input type="submit" value="Search">
    </form>
    <br>
    {% if events %}
   <table border="1" cellpadding="6">
<tr>
    <th>Event</th>
    <th>Venue</th>
    <th>Date</th>
    <th>Source</th>
    <th>Registrations</th>
    <th>Register</th>
</tr>
{% for e in events %}
<tr>
    <td>{{ e['name'] }}</td>
    <td>{{ e['venue'] }}</td>
    <td>{{ e['date'] }}</td>
    <td>{{ e['source'] }}</td>
    <td>
        {{ e['registrations'] }}
        {% if e['registered_users'] %}
        <span title="{{ ', '.join(e['registered_users']) }}">ℹ️</span>
        {% endif %}
    </td>
    <td>
        <form method="POST" action="/register">
            <input type="hidden" name="event_name" value="{{ e['name'] }}">
            <input type="hidden" name="event_date" value="{{ e['date'] }}">
            <input type="hidden" name="source" value="{{ e['source'] }}">
            Your Email: <input type="email" name="email" required>
            <button type="submit">Register</button>
        </form>
    </td>
</tr>
{% endfor %}
</table>

    {% elif city %}
        <p>No events found for "{{ city }}". Check console for API logs.</p>
    {% endif %}
    """
    return render_template_string(html, events=events, city=city, from_date=from_date, to_date=to_date)

@app.route('/register', methods=['POST'])
def register_event():
    init_db()
    email = request.form['email']
    event_name = request.form['event_name']
    event_date = request.form['event_date']
    source = request.form['source']
    register_user(email, event_name, event_date, source)
    return redirect(url_for('home'))

# ==============================
# 🔹 Run App
# ==============================
if __name__ == '__main__':
    print("🚀 Running Global Event Finder → http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001)
