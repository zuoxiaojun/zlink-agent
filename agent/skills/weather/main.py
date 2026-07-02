import requests
import sys

def get_weather(city):
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=zh&format=json"
        res = requests.get(url, timeout=10)
        pos = res.json()["results"][0]
        
        lat = pos["latitude"]
        lon = pos["longitude"]
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m&timezone=auto"
        weather_data = requests.get(w_url, timeout=10).json()["current"]
        
        return f"{city} 实时天气：温度 {weather_data['temperature_2m']}℃，风速 {weather_data['wind_speed_10m']} km/h"
    except Exception as e:
        return f"获取天气失败：{e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python main.py 城市名")
    else:
        print(get_weather(sys.argv[1]))