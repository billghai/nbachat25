import requests
import json
from datetime import datetime, timedelta
import pytz

# API setup
RAPIDAPI_KEY = "1f4a859e96msh09031c2d985e67dp1299f6jsnd61bdcf70d3a"
RAPIDAPI_HOST = "api-nba-v1.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST
}
SERIES_JSON = "series.json"

def fetch_games(date):
    url = "https://api-nba-v1.p.rapidapi.com/games"
    params = {"season": "2024", "date": date}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("api", {}).get("games", [])
    except Exception as e:
        print(f"Error fetching games for {date}: {e}")
        return []

def update_known_series():
    # Load existing series
    try:
        with open(SERIES_JSON, "r") as f:
            known_series = json.load(f)
    except FileNotFoundError:
        known_series = {}

    # Fetch games for the past 7 days
    pdt = pytz.timezone("US/Pacific")
    today = datetime.now(pdt).strftime("%Y-%m-%d")
    for i in range(7):
        date = (datetime.now(pdt) - timedelta(days=i)).strftime("%Y-%m-%d")
        games = fetch_games(date)
        for game in games:
            home_team = game["hTeam"]["fullName"]
            away_team = game["vTeam"]["fullName"]
            game_date = game["date"]["startDate"][:10]
            series_key = f"{away_team} vs {home_team} {game_date}"
            status = game.get("seriesStatus", "Unknown")
            if "win" in status.lower() or "lead" in status.lower():
                known_series[series_key] = status
            else:
                # Parse score to determine status
                home_score = int(game["hTeam"]["score"]["points"])
                away_score = int(game["vTeam"]["score"]["points"])
                series_info = game.get("playoffSeries", {})
                if series_info:
                    home_wins = series_info.get("homeWins", 0)
                    away_wins = series_info.get("awayWins", 0)
                    if home_wins == 4:
                        known_series[series_key] = f"{home_team} win 4-{away_wins}"
                    elif away_wins == 4:
                        known_series[series_key] = f"{away_team} win 4-{home_wins}"
                    else:
                        leader = home_team if home_wins > away_wins else away_team
                        known_series[series_key] = f"{leader} lead {max(home_wins, away_wins)}-{min(home_wins, away_wins)}"

    # Save updated series
    with open(SERIES_JSON, "w") as f:
        json.dump(known_series, f, indent=2)
    print(f"Updated {SERIES_JSON} with {len(known_series)} series")

if __name__ == "__main__":
    update_known_series()