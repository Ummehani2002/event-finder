
from flask import Flask, request, render_template_string
import requests
from datetime import datetime
import pytz

app = Flask(__name__)

# ==============================
# 🔑 API KEYS (replace with your real tokens)
# ==============================
PREDICTHQ_TOKEN = "m9JDCA4YL0tZd-BmHUUSZ2yC8XCy5nEsnX2GqwbU"
TICKETMASTER_KEY = "6cXVG6fHpIPTcgukSSZaPwrWAQWbEGs9"
EVENTBRITE_TOKEN = "ZIOQK747HSGPDRDQWXUY"
FACEBOOK_ACCESS_TOKEN = "YOUR_FACEBOOK_ACCESS_TOKEN"
TWITTER_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAALbp4wEAAAAAVUvdZxe8rdJf6rpcbQA6e45suTA%3Dtu2sjDsAZxhcjeXaf0bPuTqZsydmkBMztHwMzJEDNYMxLs1vxd"

# ==============================
# 🔹 PREDICTHQ
# ==============================
def fetch_predicthq_events(city, from_date, to_date):
    url = "https://api.predicthq.com/v1/events/"
    headers = {"Authorization": f"Bearer {PREDICTHQ_TOKEN}"}
    params = {
        "q": city,
        "active.gte": from_date,
        "active.lte": to_date,
        "limit": 30,
        "sort": "start"
    }

    events = []
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
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


# ==============================
# 🔹 TICKETMASTER
# ==============================
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


# ==============================
# 🔹 EVENTBRITE
# ==============================
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
# 🔹 FACEBOOK EVENTS
# ==============================
def fetch_facebook_events(city, from_date, to_date):
    url = f"https://graph.facebook.com/v19.0/search"
    params = {
        "type": "event",
        "q": city,
        "fields": "name,place,start_time",
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "limit": 30
    }

    events = []
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for e in data.get("data", []):
            start_time = e.get("start_time", "N/A")
            if from_date <= start_time[:10] <= to_date:
                events.append({
                    "name": e.get("name", "N/A"),
                    "venue": e.get("place", {}).get("name", "N/A"),
                    "date": start_time,
                    "source": "Facebook"
                })
    except Exception as ex:
        print("Facebook error:", ex)
    return events

import re

def extract_event_info_from_tweet(tweet_text, city):
    """
    Attempts to extract clean event info from a tweet text.
    Returns a dict with name, date (if found), and venue.
    """
    # Pattern: "Event: XYZ Dates: ... Location: ..."
    match_name = re.search(r"Event:\s*(.+?)\s+Dates:", tweet_text, re.IGNORECASE)
    match_dates = re.search(r"Dates:\s*(.+?)\s+Location:", tweet_text, re.IGNORECASE)
    match_location = re.search(r"Location:\s*(.+?)(\.|$|\s)", tweet_text, re.IGNORECASE)

    if match_name and match_dates and match_location:
        return {
            "name": match_name.group(1).strip(),
            "venue": match_location.group(1).strip(),
            "date": match_dates.group(1).strip()
        }

    # Fallback: look for capitalized words followed by 'in City'
    fallback = re.search(r"([A-Z][\w\s]{3,50})\s+in\s+" + re.escape(city), tweet_text)
    if fallback:
        return {
            "name": fallback.group(1).strip(),
            "venue": city,
            "date": None
        }

    return None

# ==============================
# 🔹 TWITTER / X EVENTS
# ==============================
# ==============================
# 🔹 TWITTER / X EVENTS
# ==============================
def fetch_twitter_events(city, from_date, to_date):
    url = "https://api.x.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    query = f"event {city} lang:en -is:retweet"
    params = {"query": query, "max_results": 20, "tweet.fields": "created_at"} 

    events = []
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()

        for t in data.get("data", []):
            tweet_text = t.get("text", "")

            # Skip obvious promotional tweets
            if "promo code" in tweet_text.lower():
                continue

            # Extract clean event info
            info = extract_event_info_from_tweet(tweet_text, city)
            if info:
                events.append({
                    "name": info['name'],
                    "venue": info['venue'],
                    "date": info['date'] if info['date'] else t.get("created_at", "N/A"),
                    "source": "Twitter"
                })

    except Exception as ex:
        print("Twitter error:", ex)

    return events




# ==============================
# 🔹 UTC → Local Time
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
# 🔹 FLASK ROUTE
# ==============================
@app.route('/', methods=['GET', 'POST'])
def home():
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
            all_events.extend(fetch_facebook_events(city, from_date, to_date))
            all_events.extend(fetch_twitter_events(city, from_date, to_date))

            # Deduplicate
            seen = set()
            for e in all_events:
                key = (e['name'].lower(), e['date'])
                if key not in seen:
                    seen.add(key)
                    events.append(e)

            # Convert timezones
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

    html = """
    <h2> Global Event Finder </h2>
    <form method="POST">
        City: <input type="text" name="city" value="{{ city }}" required>
        From: <input type="date" name="from_date" value="{{ from_date }}" required>
        To: <input type="date" name="to_date" value="{{ to_date }}" required>
        <input type="submit" value="Search">
    </form>
    <br>
    {% if events %}
        <table border="1" cellpadding="6">
            <tr><th>Event</th><th>Venue</th><th>Date</th><th>Source</th></tr>
            {% for e in events %}
            <tr>
                <td>{{ e['name'] }}</td>
                <td>{{ e['venue'] }}</td>
                <td>{{ e['date'] }}</td>
                <td>{{ e['source'] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% elif city %}
        <p>No events found for "{{ city }}"</p>
    {% endif %}
    """
    return render_template_string(html, events=events, city=city, from_date=from_date, to_date=to_date)


if __name__ == '__main__':
    print(" Running Global Event Finder → http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001)
