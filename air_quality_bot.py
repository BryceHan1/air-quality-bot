import requests
import schedule
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ===== 配置项 =====
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"
AQICN_TOKEN = "你的aqicn token"
CITY = "el-paso"

# ===== 初始化状态记录 =====
last_status = {
    "alert": False,
    "duststorm": False,
    "uv_alert": False
}

# ===== 发送企业微信消息 =====
def send_wechat_message(msg):
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": msg
        }
    }
    requests.post(WEBHOOK_URL, json=data)

# ===== 获取空气质量数据 =====
def fetch_air_quality():
    url = f"https://api.waqi.info/feed/{CITY}/?token={AQICN_TOKEN}"
    response = requests.get(url)
    data = response.json()
    if data["status"] == "ok":
        iaqi = data["data"]["iaqi"]
        aqi = data["data"].get("aqi", 0)
        pm25 = iaqi.get("pm25", {}).get("v", 0)
        pm10 = iaqi.get("pm10", {}).get("v", 0)
        uv = iaqi.get("uv", {}).get("v", 0)
        return aqi, pm25, pm10, uv
    else:
        raise Exception("❌ 获取数据失败")

# ===== 检查预警并发送消息 =====
def check_and_alert():
    try:
        aqi, pm25, pm10, uv = fetch_air_quality()
        now = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")  # UTC-6

        alerts = []
        tips = []

        if aqi > 100:
            alerts.append(f"**AQI: {aqi}**（超标）")
            tips.append("空气质量较差，建议减少户外活动，佩戴口罩。")

        if pm25 > 35:
            alerts.append(f"**PM2.5: {pm25}**（超标）")
            tips.append("PM2.5影响呼吸系统，建议佩戴口罩，开启空气净化器。")
        if pm25 > 70:
            alerts.append(f"**PM2.5: {pm25}**（严重超标）")
            tips.append("PM2.5严重污染，建议避免外出。")

        if pm10 > 50:
            alerts.append(f"**PM10: {pm10}**（超标）")
            tips.append("PM10可能引发呼吸不适，注意防护。")
        if pm10 > 100:
            alerts.append(f"**PM10: {pm10}**（严重超标）")
            tips.append("PM10严重污染，请关闭门窗，减少外出。")

        if pm10 > 150 and pm25 > 30:
            alerts.append(f"**沙尘暴预警**（PM10: {pm10}, PM2.5: {pm25}）")
            tips.append("可能出现沙尘暴，建议留在室内，注意防尘防护。")
            last_status["duststorm"] = True

        if uv >= 6:
            alerts.append(f"**UV Index: {uv}**（高）")
            tips.append("紫外线较强，建议使用防晒霜、遮阳帽等防护。")
            last_status["uv_alert"] = True
        if uv >= 8:
            alerts.append(f"**UV Index: {uv}**（非常高）")
            tips.append("紫外线非常强烈，请避免长时间阳光暴晒。")
            last_status["uv_alert"] = True

        if alerts:
            msg = f"⚠️ **空气质量预警**\n\n**时间：** {now}\n**超标指标：**\n- " + "\n- ".join(alerts)
            if tips:
                msg += "\n\n**防护建议：**\n- " + "\n- ".join(tips)
            send_wechat_message(msg)
            last_status["alert"] = True
        else:
            if last_status["alert"] or last_status["duststorm"] or last_status["uv_alert"]:
                msg = (
                    f"✅ 空气质量恢复正常（{now}）\n"
                    f"- AQI: {aqi}\n"
                    f"- PM2.5: {pm25}\n"
                    f"- PM10: {pm10}\n"
                    f"- UV Index: {uv}"
                )
                send_wechat_message(msg)
                last_status["alert"] = False
                last_status["duststorm"] = False
                last_status["uv_alert"] = False
            else:
                print("✅ 当前空气质量良好，无需提醒。")

    except Exception as e:
        print(f"❌ 检查异常: {e}")

# ===== Flask 保活服务 =====
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===== 定时任务（每天六个时间点） =====
schedule.every().day.at("08:30").do(check_and_alert)
schedule.every().day.at("10:30").do(check_and_alert)
schedule.every().day.at("12:00").do(check_and_alert)
schedule.every().day.at("14:00").do(check_and_alert)
schedule.every().day.at("16:00").do(check_and_alert)
schedule.every().day.at("18:00").do(check_and_alert)

# ===== 启动程序 =====
print("✅ 空气质量监控已启动...")
check_and_alert()
keep_alive()

while True:
    schedule.run_pending()
    time.sleep(60)
