#!/usr/bin/env python3
"""
Aviation Briefing Server - WX / TAF / NOTAM 判读智能体后端
"""
import json
import re
import html
import os
import io
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ── Simple cache ──────────────────────────────────────────────────
_notam_cache = {}  # {icao: (timestamp, data)}
_coord_cache = {}  # {icao: (lat, lon, name) | None}  机场坐标解析缓存
_wx_cache = {}    # {(icao, date, hour): (timestamp, data)}
_taf_cache = {}   # {(icao, date, h, m): (timestamp, data)}
_cache_lock = threading.Lock()

# ── Airport database ──────────────────────────────────────────────
AIRPORTS = {
    'RCTP': (25.0777, 121.2328, '台北桃园'),
    'RJBB': (34.432, 135.2304, '大阪关西'),
    'RJTT': (35.5494, 139.7798, '东京羽田'),
    'RKSI': (37.4602, 126.4407, '首尔仁川'),
    'VHHH': (22.308, 113.9185, '香港'),
    'VMMC': (22.1496, 113.5924, '澳门'),
    'VTBS': (13.6811, 100.7473, '曼谷素万那普'),
    'WMKK': (2.7456, 101.7099, '吉隆坡'),
    'WSSS': (1.3592, 103.9894, '新加坡樟宜'),
    'ZBAA': (40.0773, 116.5967, '北京首都'),
    'ZBAD': (39.5013, 116.414, '北京大兴'),
    'ZBCD': (41.1225, 118.0739, '承德'),
    'ZBCF': (42.1597, 118.841, '赤峰'),
    'ZBCZ': (36.2475, 113.126, '长治'),
    'ZBDH': (39.6664, 119.0614, '秦皇岛北戴河'),
    'ZBDS': (39.4935, 109.8599, '鄂尔多斯'),
    'ZBDT': (40.0614, 113.4805, '大同'),
    'ZBER': (43.4241, 112.0911, '二连浩特赛乌苏'),
    'ZBES': (47.3106, 119.9117, '阿尔山'),
    'ZBHD': (36.5248, 114.4241, '邯郸'),
    'ZBHH': (40.8497, 111.8246, '呼和浩特'),
    'ZBHZ': (45.4872, 119.4072, '霍林郭勒'),
    'ZBLA': (49.2086, 119.8223, '海拉尔'),
    'ZBLF': (36.1326, 111.6412, '临汾'),
    'ZBLL': (37.6833, 111.1428, '吕梁'),
    'ZBMZ': (49.5667, 117.33, '满洲里'),
    'ZBOW': (40.56, 109.997, '包头东河'),
    'ZBSG': (39.2732, 112.6916, '朔州滋润'),
    'ZBSJ': (38.2807, 114.697, '石家庄'),
    'ZBSN': (39.7178, 118.0026, '唐山三女河'),
    'ZBTJ': (39.1244, 117.346, '天津'),
    'ZBTL': (43.5567, 122.2, '通辽'),
    'ZBUC': (41.1303, 113.1073, '乌兰察布'),
    'ZBUH': (39.7934, 106.7993, '乌海'),
    'ZBUL': (46.1953, 122.0083, '乌兰浩特'),
    'ZBUT': (41.6944, 108.3784, '乌拉特中旗'),
    'ZBXH': (43.9156, 115.964, '锡林浩特'),
    'ZBXZ': (38.5975, 112.9692, '忻州'),
    'ZBYC': (35.1178, 111.034, '运城关公'),
    'ZBYN': (37.7469, 112.628, '太原'),
    'ZBYZ': (40.9264, 107.7409, '巴彦淖尔'),
    'ZBZJ': (40.7387, 114.9334, '张家口宁远'),
    'ZBZL': (47.8659, 122.7687, '扎兰屯'),
    'ZGBH': (21.5387, 109.2937, '北海'),
    'ZGBS': (23.7206, 106.96, '百色右江'),
    'ZGCD': (28.9189, 111.64, '常德'),
    'ZGCJ': (27.4431, 109.7047, '怀化'),
    'ZGCZ': (25.7534, 112.8454, '郴州'),
    'ZGDY': (29.1047, 110.4428, '张家界荷花'),
    'ZGFS': (23.0825, 113.0708, '佛山'),
    'ZGGG': (23.3924, 113.299, '广州白云'),
    'ZGHA': (28.1892, 113.22, '长沙黄花'),
    'ZGHC': (24.8043, 107.7108, '河池'),
    'ZGHY': (26.7221, 112.618, '衡阳'),
    'ZGHZ': (23.05, 114.6, '惠州'),
    'ZGKL': (25.2198, 110.0396, '桂林'),
    'ZGLG': (26.3387, 111.61, '永州'),
    'ZGMX': (24.2634, 116.0979, '梅州'),
    'ZGNN': (22.5981, 108.1819, '南宁吴圩'),
    'ZGOW': (23.552, 116.5033, '揭阳'),
    'ZGSD': (22.0064, 113.376, '珠海金湾'),
    'ZGSY': (26.8061, 110.641, '邵阳'),
    'ZGSZ': (22.6395, 113.8033, '深圳宝安'),
    'ZGWZ': (23.4032, 111.0933, '梧州'),
    'ZGXX': (28.4972, 109.5218, '湘西'),
    'ZGYL': (22.433, 110.12, '玉林'),
    'ZGYY': (29.3117, 113.2816, '岳阳'),
    'ZGZH': (24.2075, 109.391, '柳州'),
    'ZGZJ': (21.4817, 110.5903, '湛江'),
    'ZHCC': (34.5265, 113.8492, '郑州'),
    'ZHEC': (30.3412, 115.0393, '鄂州'),
    'ZHES': (30.3203, 109.485, '恩施'),
    'ZHHH': (30.7748, 114.2137, '武汉'),
    'ZHJZ': (30.2928, 112.4485, '荆州'),
    'ZHLY': (34.7411, 112.388, '洛阳'),
    'ZHNY': (32.9827, 112.6175, '南阳'),
    'ZHQQ': (35.8708, 114.4619, '安阳'),
    'ZHSN': (31.626, 110.34, '神农架'),
    'ZHSY': (32.5929, 110.9063, '十堰'),
    'ZHXF': (32.1522, 112.2917, '襄阳'),
    'ZHXY': (32.5408, 114.0791, '信阳明港'),
    'ZHYC': (30.5541, 111.4826, '宜昌'),
    'ZJHK': (19.9349, 110.459, '海口'),
    'ZJQH': (19.141, 110.4528, '琼海'),
    'ZJSY': (18.3029, 109.412, '三亚'),
    'ZLAK': (32.757, 108.8734, '安康'),
    'ZLDH': (40.162, 94.8128, '敦煌'),
    'ZLDL': (37.1253, 97.2687, '德令哈'),
    'ZLGL': (34.4181, 100.3011, '果洛玛沁'),
    'ZLGM': (36.4006, 94.7861, '格尔木'),
    'ZLGY': (36.0789, 106.2169, '固原'),
    'ZLHB': (38.0081, 100.6451, '海北祁连'),
    'ZLHX': (38.2016, 90.8378, '茫崖花土沟'),
    'ZLHZ': (33.1335, 107.2038, '汉中西关'),
    'ZLIC': (38.3228, 106.3932, '银川河东'),
    'ZLJC': (38.5422, 102.3483, '金昌'),
    'ZLJQ': (39.8591, 98.3393, '嘉峪关'),
    'ZLLL': (36.5152, 103.62, '兰州中川'),
    'ZLLN': (33.7899, 105.79, '陇南'),
    'ZLQY': (35.8026, 107.5989, '庆阳'),
    'ZLTS': (34.5601, 105.8603, '天水麦积山'),
    'ZLXH': (34.819, 102.6223, '甘南夏河'),
    'ZLXN': (36.5277, 102.0402, '西宁'),
    'ZLXY': (34.4422, 108.7624, '西安咸阳'),
    'ZLYA': (36.4794, 109.4641, '延安南泥湾'),
    'ZLYL': (38.3597, 109.5909, '榆林'),
    'ZLYS': (32.8364, 97.0364, '玉树'),
    'ZLZW': (37.5731, 105.1545, '中卫'),
    'ZLZY': (38.8019, 100.675, '张掖甘州'),
    'ZPBS': (25.0533, 99.1683, '保山'),
    'ZPCW': (23.2763, 99.3732, '沧源'),
    'ZPDL': (25.6494, 100.319, '大理'),
    'ZPDQ': (27.7936, 99.6772, '迪庆香格里拉'),
    'ZPJH': (21.9746, 100.7622, '景洪'),
    'ZPJM': (22.4177, 99.784, '澜沧'),
    'ZPLC': (23.7381, 100.025, '临沧'),
    'ZPLJ': (26.6775, 100.2449, '丽江三义'),
    'ZPMS': (24.4011, 98.5317, '芒市'),
    'ZPPP': (25.1103, 102.9367, '昆明'),
    'ZPSM': (22.7933, 100.959, '思茅'),
    'ZPWS': (23.5583, 104.3255, '文山'),
    'ZSAM': (24.5439, 118.1275, '厦门高崎'),
    'ZSAQ': (30.5822, 117.05, '安庆'),
    'ZSCG': (31.9205, 119.7755, '常州'),
    'ZSCN': (28.8648, 115.9027, '南昌'),
    'ZSDY': (37.5014, 118.7899, '东营'),
    'ZSFY': (32.8822, 115.7344, '阜阳'),
    'ZSFZ': (25.9293, 119.6725, '福州'),
    'ZSGZ': (25.8533, 114.7789, '赣州'),
    'ZSHC': (30.2361, 120.4289, '杭州萧山'),
    'ZSHZ': (35.213, 115.7367, '菏泽'),
    'ZSJD': (29.3386, 117.176, '景德镇'),
    'ZSJG': (35.6474, 116.7433, '济宁大安'),
    'ZSJJ': (29.4769, 115.8011, '九江'),
    'ZSJN': (36.8572, 117.216, '济南'),
    'ZSJU': (28.9661, 118.8988, '衢州'),
    'ZSLG': (34.4141, 119.179, '连云港'),
    'ZSLO': (25.6759, 116.7459, '龙岩'),
    'ZSLQ': (28.5622, 121.429, '台州'),
    'ZSLY': (35.0529, 118.4118, '临沂'),
    'ZSNB': (29.8267, 121.462, '宁波'),
    'ZSNJ': (31.735, 118.8659, '南京'),
    'ZSNT': (32.0736, 120.9801, '南通'),
    'ZSOF': (31.9878, 116.9769, '合肥'),
    'ZSPD': (31.1434, 121.805, '上海浦东'),
    'ZSQD': (36.362, 120.0882, '青岛'),
    'ZSQZ': (24.7959, 118.5886, '泉州'),
    'ZSRZ': (35.405, 119.3244, '日照'),
    'ZSSH': (33.7927, 119.1267, '淮安涟水'),
    'ZSSM': (26.4263, 117.8336, '三明'),
    'ZSSR': (28.3797, 117.9643, '上饶'),
    'ZSSS': (31.1981, 121.3343, '上海虹桥'),
    'ZSTX': (29.7333, 118.256, '黄山'),
    'ZSWA': (31.1045, 118.6669, '芜湖'),
    'ZSWF': (36.6467, 119.119, '潍坊'),
    'ZSWH': (37.1871, 122.229, '威海'),
    'ZSWX': (31.497, 120.4304, '无锡'),
    'ZSWY': (27.7019, 118.001, '武夷山'),
    'ZSWZ': (27.9106, 120.8535, '温州永强'),
    'ZSXZ': (34.0591, 117.5553, '徐州观音'),
    'ZSYA': (32.5634, 119.7198, '扬州'),
    'ZSYC': (27.8025, 114.3062, '宜春明月山'),
    'ZSYN': (33.4283, 120.2054, '盐城'),
    'ZSYT': (37.6597, 120.9781, '烟台'),
    'ZSYW': (29.3421, 120.0312, '义乌'),
    'ZSZS': (29.9339, 122.3623, '舟山'),
    'ZUAL': (32.0979, 80.054, '阿里'),
    'ZUAS': (26.2606, 105.8733, '安顺'),
    'ZUBD': (30.5536, 97.1083, '昌都'),
    'ZUBJ': (27.2671, 105.4721, '毕节'),
    'ZUCK': (29.7123, 106.6519, '重庆'),
    'ZUDA': (31.0488, 107.4356, '达州金垭'),
    'ZUDC': (29.3163, 100.0603, '稻城'),
    'ZUDX': (31.1302, 107.4295, '达州'),
    'ZUGU': (32.3903, 105.6946, '广元'),
    'ZUGY': (26.5418, 106.804, '贵阳'),
    'ZUGZ': (31.7575, 99.5542, '甘孜'),
    'ZUJZ': (32.8533, 103.6822, '九寨黄龙'),
    'ZUKD': (30.1425, 101.7387, '康定'),
    'ZUKJ': (26.972, 107.988, '凯里'),
    'ZULB': (25.4525, 107.9617, '荔波'),
    'ZULS': (29.298, 90.912, '拉萨'),
    'ZULZ': (29.0304, 105.4684, '泸州'),
    'ZUMT': (27.9618, 106.4354, '遵义'),
    'ZUMY': (31.4281, 104.741, '绵阳'),
    'ZUNC': (30.7981, 106.1642, '南充'),
    'ZUNP': (26.3222, 109.1499, '黎平'),
    'ZUNZ': (29.3033, 94.3353, '林芝米林'),
    'ZUPS': (26.6094, 104.979, '六盘水'),
    'ZUQJ': (29.5133, 108.8311, '黔江'),
    'ZURK': (29.3509, 89.2992, '日喀则'),
    'ZUSH': (28.4224, 92.3481, '山南隆子'),
    'ZUTC': (24.9381, 98.4858, '腾冲'),
    'ZUTF': (30.3125, 104.4413, '成都天府'),
    'ZUTR': (27.8833, 109.3089, '铜仁'),
    'ZUUU': (30.5583, 103.946, '成都双流'),
    'ZUWL': (29.4657, 107.6937, '武隆'),
    'ZUWS': (31.069, 109.709, '巫山'),
    'ZUWX': (30.8017, 108.433, '万州五桥'),
    'ZUXC': (27.9891, 102.184, '西昌'),
    'ZUYB': (28.8584, 104.5262, '宜宾'),
    'ZUYI': (25.0834, 104.9608, '兴义'),
    'ZUZH': (26.54, 101.7985, '攀枝花保安营'),
    'ZUZY': (27.8107, 107.2472, '遵义'),
    'ZWAK': (41.2625, 80.2917, '阿克苏'),
    'ZWAL': (40.4347, 81.2621, '阿拉尔'),
    'ZWAT': (47.7499, 88.0858, '阿勒泰'),
    'ZWBL': (44.8955, 82.3001, '博乐'),
    'ZWCM': (38.2345, 85.4655, '且末'),
    'ZWFY': (46.8042, 89.512, '富蕴'),
    'ZWHM': (42.8414, 93.6692, '哈密'),
    'ZWHZ': (44.2421, 85.8905, '石河子'),
    'ZWKC': (41.6779, 82.8729, '库车龟兹'),
    'ZWKL': (41.615, 86.1408, '库尔勒'),
    'ZWKM': (45.4665, 84.9527, '克拉玛依'),
    'ZWKN': (48.2223, 86.9959, '布尔津'),
    'ZWNL': (43.4318, 83.3786, '新源'),
    'ZWRQ': (38.9747, 88.0083, '若羌'),
    'ZWSC': (38.2454, 77.0561, '莎车'),
    'ZWSH': (39.5423, 76.0202, '喀什'),
    'ZWTC': (46.6725, 83.3408, '塔城'),
    'ZWTL': (43.0308, 89.0987, '吐鲁番'),
    'ZWTN': (37.0385, 79.8649, '和田'),
    'ZWWW': (43.9136, 87.4794, '乌鲁木齐地窝堡'),
    'ZWYN': (43.9558, 81.3303, '伊宁'),
    'ZWYT': (36.8085, 81.7827, '于田'),
    'ZYAS': (41.1053, 122.854, '鞍山'),
    'ZYBA': (45.5053, 123.0197, '白城'),
    'ZYBS': (42.0669, 127.6022, '白山'),
    'ZYCC': (43.9962, 125.685, '长春'),
    'ZYCH': (39.2664, 122.667, '长海'),
    'ZYCY': (41.5381, 120.435, '朝阳'),
    'ZYDD': (40.0255, 124.2867, '丹东'),
    'ZYDQ': (46.7509, 125.1386, '大庆'),
    'ZYDU': (48.441, 126.1284, '五大连池'),
    'ZYFY': (48.1972, 134.363, '抚远'),
    'ZYHB': (45.6234, 126.25, '哈尔滨'),
    'ZYHE': (50.1716, 127.3089, '黑河'),
    'ZYJD': (50.3714, 124.1175, '加格达奇'),
    'ZYJM': (46.8428, 130.4643, '佳木斯东郊'),
    'ZYJS': (47.1082, 132.6579, '建三江'),
    'ZYJX': (45.293, 131.193, '鸡西'),
    'ZYJZ': (40.936, 121.2771, '锦州'),
    'ZYLD': (47.7521, 129.0191, '伊春林都'),
    'ZYMD': (44.5252, 129.5686, '牡丹江'),
    'ZYMH': (52.9169, 122.4228, '漠河'),
    'ZYQQ': (47.23, 123.9142, '齐齐哈尔三家子'),
    'ZYSQ': (44.9311, 124.5521, '松原查干湖'),
    'ZYTL': (38.9657, 121.5385, '大连'),
    'ZYTN': (42.0484, 125.734, '通化'),
    'ZYTX': (41.6398, 123.4837, '沈阳桃仙'),
    'ZYYJ': (42.8828, 129.451, '延吉'),
    'ZYYK': (40.5425, 122.3586, '营口'),
}

# ── WX Code mapping ───────────────────────────────────────────────
WX_NAME = {
    0: 'SKC', 1: 'FEW', 2: 'SCT', 3: 'BKN',
    45: 'FG', 48: 'FZFG',
    51: 'DZ', 53: 'DZ', 55: 'DZ',
    61: 'RA', 63: 'RA', 65: 'RA',
    71: 'SN', 73: 'SN', 75: 'SN',
    80: 'SHRA', 81: 'SHRA', 82: 'SHRA',
    95: 'TS', 96: 'TSGR',
}

# ── Helpers ───────────────────────────────────────────────────────
def fetch_url(url, timeout=15):
    """Fetch URL with proper headers and proxy support."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/json,text/plain,*/*',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    try:
        with _build_opener().open(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception:
        return None

def bjt_to_utc(bjt_str):
    """Convert BJT HHMM to UTC hours. Returns (utc_hour, minute)."""
    try:
        h = int(bjt_str[:2])
        m = int(bjt_str[2:4])
        utc_h = (h - 8) % 24
        return utc_h, m
    except:
        return None, None

def bjt_datetime_to_utc_date(date_str, bjt_time_str, is_arrival_next_day=False):
    """Given a BJT date and HHMM time, return the UTC date string and UTC hour.
    Handles day rollover when BJT hour < 8 (UTC is previous day)."""
    try:
        bjt_date = datetime.strptime(date_str, '%Y-%m-%d')
        if is_arrival_next_day:
            bjt_date += timedelta(days=1)
        bjt_hour = int(bjt_time_str[:2])
        bjt_min = int(bjt_time_str[2:4])
        bjt_dt = bjt_date.replace(hour=bjt_hour, minute=bjt_min)
        utc_dt = bjt_dt - timedelta(hours=8)
        return utc_dt.strftime('%Y-%m-%d'), utc_dt.hour, utc_dt.minute
    except:
        return None, None, None

def risk_wx(pop, vis, ws_code):
    """Determine WX risk level."""
    is_ts = ws_code in (95, 96)
    # HIGH: TS, or vis below CAT I minima (550m), or heavy rain with low vis
    if is_ts or (vis is not None and vis < 800):
        return 'HIGH'
    if (pop is not None and pop > 70 and vis is not None and vis < 3000):
        return 'HIGH'
    # MED: moderate rain probability, or vis 800-5000m
    if (pop is not None and 30 <= pop <= 70) or (vis is not None and 800 <= vis <= 5000):
        return 'MED'
    return 'LOW'

# ── WX ────────────────────────────────────────────────────────────
def resolve_coords(icao):
    """解析机场坐标: 预置库 → AviationWeather stationinfo → None。"""
    if icao in AIRPORTS:
        return AIRPORTS[icao]
    if icao in _coord_cache:
        return _coord_cache[icao]
    result = None
    try:
        txt = fetch_url(f'https://aviationweather.gov/api/data/stationinfo?ids={icao}&format=json', timeout=10)
        if txt:
            arr = json.loads(txt)
            if isinstance(arr, list) and arr and arr[0].get('lat') is not None:
                result = (float(arr[0]['lat']), float(arr[0]['lon']), arr[0].get('site') or icao)
    except Exception:
        result = None
    _coord_cache[icao] = result
    return result

def get_wx(icao, date_str, target_hour_bjt):
    """Fetch hourly weather from Open-Meteo for a target BJT hour."""
    coords = resolve_coords(icao)
    if not coords:
        return None
    lat, lon, name = coords
    url = (
        f'https://api.open-meteo.com/v1/forecast?'
        f'latitude={lat}&longitude={lon}'
        '&hourly=precipitation,precipitation_probability,rain,'
        'wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility,weather_code'
        f'&start_date={date_str}&end_date={date_str}'
        '&timezone=Asia%2FShanghai&wind_speed_unit=ms'
    )
    try:
        data = json.loads(fetch_url(url))
        if not data or 'hourly' not in data:
            return None
        h = data['hourly']
        # Find target hour
        target_key = f'{date_str}T{target_hour_bjt:02d}:00'
        if target_key not in h['time']:
            return None
        i = h['time'].index(target_key)
        return {
            'icao': icao,
            'time': target_key,
            'precip': h['precipitation'][i],
            'pop': h['precipitation_probability'][i],
            'rain': h['rain'][i],
            'wind_spd': h['wind_speed_10m'][i],
            'wind_dir': h['wind_direction_10m'][i],
            'wind_gst': h['wind_gusts_10m'][i],
            'vis': h['visibility'][i],
            'wx_code': h['weather_code'][i],
            'wx_name': WX_NAME.get(h['weather_code'][i], str(h['weather_code'][i])),
        }
    except Exception as e:
        return None

# ── TAF ───────────────────────────────────────────────────────────
def taf_icao_of(raw):
    """从TAF原始文本提取ICAO四字码（用于把粘贴的TAF归属到对应机场）。"""
    m = re.search(r'TAF\s+(?:AMD\s+|COR\s+)?([A-Z]{4})', raw or '')
    return m.group(1) if m else ''

def parse_taf_issue(raw_taf):
    """Extract ISSUE time from raw TAF text."""
    m = re.search(r'TAF\s+\w+\s+(\d{6})Z', raw_taf)
    if m:
        return m.group(1) + 'Z'
    return None

def parse_taf_valid(raw_taf):
    """Extract VALID period from raw TAF text."""
    m = re.search(r'TAF\s+\w+\s+\d{6}Z\s+(\d{4}/\d{4})', raw_taf)
    if m:
        return m.group(1)
    return None

def parse_taf_groups(raw_taf):
    """Extract BASE, TEMPO, BECMG, FM, PROB groups."""
    groups = {'BASE': '', 'TEMPO': [], 'BECMG': [], 'FM': [], 'PROB': []}
    # Remove TAF header line
    body = re.sub(r'^TAF\s+\w+\s+\d{6}Z\s+\d{4}/\d{4}\s*', '', raw_taf.strip())
    # Remove TX/TN
    body = re.sub(r'TX\d{2}/\d{4}Z\s*', '', body)
    body = re.sub(r'TN\d{2}/\d{4}Z\s*', '', body)
    # Split by change indicators
    parts = re.split(r'\s+(?=TEMPO|BECMG|FM|PROB\d{2})', body.strip())
    if parts:
        groups['BASE'] = parts[0].strip()
    for part in parts[1:]:
        m = re.match(r'(TEMPO|BECMG|FM|PROB\d{2})\s+(.*)', part)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if key.startswith('PROB'):
                groups['PROB'].append(f'{key} {val}')
            else:
                groups[key].append(f'{key} {val}')
    return groups

def taf_valid_covers(valid_str, target_utc_h, target_utc_m, date_str):
    """Check if TAF valid period covers target UTC time."""
    try:
        m = re.match(r'(\d{2})(\d{2})/(\d{2})(\d{2})', valid_str)
        if not m:
            return False
        start_day, start_h, end_day, end_h = map(int, m.groups())
        target_day = int(date_str[-2:])
        target_total = target_day * 100 + target_utc_h
        start_total = start_day * 100 + start_h
        end_total = end_day * 100 + end_h
        # Handle month rollover
        if end_total < start_total:
            if target_total < start_total:
                target_total += 3100  # add max days
            end_total += 3100
        return start_total <= target_total <= end_total
    except:
        return False

def taf_target_in_group(valid_str, group_str, target_utc_h, target_utc_m, date_str, before_h=0, after_h=0):
    """Check if target time window (target-before_h ~ target+after_h) overlaps a change group."""
    try:
        m = re.match(r'(\d{2})(\d{2})/(\d{2})(\d{2})', valid_str)
        if not m:
            return False
        target_day = int(date_str[-2:])
        t = target_day * 1440 + target_utc_h * 60 + target_utc_m
        t_start = t - before_h * 60
        t_end = t + after_h * 60

        time_match = re.search(r'(\d{2})(\d{2})/(\d{2})(\d{2})', group_str)
        if time_match:
            g_day1, g_h1, g_day2, g_h2 = map(int, time_match.groups())
            g_start = g_day1 * 1440 + g_h1 * 60
            g_end = g_day2 * 1440 + g_h2 * 60
            if g_end < g_start:
                g_end += 31 * 1440
                if t_start < g_start:
                    t_start += 31 * 1440
                    t_end += 31 * 1440
            return g_start <= t_end and g_end >= t_start
        return False
    except:
        return False

def get_taf(icao, date_str, target_utc_h, target_utc_m):
    """Fetch TAF from multiple sources, return best one."""
    sources = []

    # Source 1: AviationWeather raw
    raw_text = fetch_url(f'https://aviationweather.gov/api/data/taf?ids={icao}&format=raw')
    if raw_text and raw_text.strip():
        issue = parse_taf_issue(raw_text)
        if issue:
            sources.append(('AviationWeather RAW', raw_text.strip(), issue))

    # Source 2: AviationWeather JSON
    json_text = fetch_url(f'https://aviationweather.gov/api/data/taf?ids={icao}&format=json')
    if json_text:
        try:
            jdata = json.loads(json_text)
            if isinstance(jdata, list) and len(jdata) > 0:
                raw = jdata[0].get('rawTAF', '')
                if raw:
                    issue = parse_taf_issue(raw)
                    if issue:
                        sources.append(('AviationWeather JSON', raw, issue))
        except:
            pass

    if not sources:
        return {'error': 'NO_TAF', 'message': '无可用TAF数据'}

    # Pick latest by ISSUE
    sources.sort(key=lambda x: x[2], reverse=True)
    best_name, best_raw, best_issue = sources[0]

    valid = parse_taf_valid(best_raw)
    covers = taf_valid_covers(valid, target_utc_h, target_utc_m, date_str) if valid else False

    result = {
        'source': best_name,
        'issue': best_issue,
        'valid': valid,
        'covers': covers,
        'raw': best_raw,
    }

    if covers:
        groups = parse_taf_groups(best_raw)
        result['base'] = groups['BASE']
        result['has_tempo'] = len(groups['TEMPO']) > 0
        result['has_becmg'] = len(groups['BECMG']) > 0
        result['has_fm'] = len(groups['FM']) > 0
        result['has_prob'] = len(groups['PROB']) > 0

        # 变化组：target_groups=精确覆盖目标时刻（决定风险）；impact_groups=落入前2h~后3h影响窗口（用于高亮）
        result['target_groups'] = []
        result['impact_groups'] = []
        for g_type, g_list in [('TEMPO', groups['TEMPO']), ('BECMG', groups['BECMG']),
                                 ('FM', groups['FM']), ('PROB', groups['PROB'])]:
            for g in g_list:
                exact = taf_target_in_group(valid, g, target_utc_h, target_utc_m, date_str)
                near = taf_target_in_group(valid, g, target_utc_h, target_utc_m, date_str,
                                           WX_WIN_BEFORE, WX_WIN_AFTER)
                if exact:
                    result['target_groups'].append(g)
                elif near:
                    result['impact_groups'].append(g)

        # Risk assessment
        result['risk'] = 'LOW'
        for g in result['target_groups']:
            g_upper = g.upper()
            if any(kw in g_upper for kw in ['TSRA', '+TSRA', 'TS', '+TS', 'CB']):
                result['risk'] = 'HIGH'
            elif any(kw in g_upper for kw in ['SHRA', '+SHRA', 'RA', 'FG', 'BR']):
                if result['risk'] != 'HIGH':
                    result['risk'] = 'MED'

    return result

# ── Cached wrappers (avoid double-fetch when AI agent + brief both run) ──
def get_wx_cached(icao, date_str, target_hour_bjt):
    key = (icao, date_str, target_hour_bjt)
    now = datetime.now(timezone.utc)
    with _cache_lock:
        hit = _wx_cache.get(key)
        if hit and (now - hit[0]).total_seconds() < 600:
            return hit[1]
    val = get_wx(icao, date_str, target_hour_bjt)
    if val:
        with _cache_lock:
            _wx_cache[key] = (now, val)
    return val

def get_taf_cached(icao, date_str, target_utc_h, target_utc_m):
    key = (icao, date_str, target_utc_h, target_utc_m)
    now = datetime.now(timezone.utc)
    with _cache_lock:
        hit = _taf_cache.get(key)
        if hit and (now - hit[0]).total_seconds() < 600:
            return hit[1]
    val = get_taf(icao, date_str, target_utc_h, target_utc_m)
    if val and not val.get('error'):
        with _cache_lock:
            _taf_cache[key] = (now, val)
    return val

# ── NOTAM ─────────────────────────────────────────────────────────
def notam_series_offset(notam_id):
    """通告系列字母决定时间基准: C/K = 北京时(BJT, UTC+8); 其余(A/E/F/G/L/U/W/Y…) = UTC。"""
    s = str(notam_id or '').strip().upper()[:1]
    return timedelta(hours=-8) if s in ('C', 'K') else timedelta(0)

def check_notam_expired(expires_str, notam_id=None):
    """Check if NOTAM has expired (series-aware timezone)."""
    now = datetime.now(timezone.utc)
    # Strip timezone suffix and normalize
    expires_str = (expires_str or '').strip()
    expires_str = re.sub(r'\s+UTC$', '', expires_str, flags=re.IGNORECASE)

    if 'UNTIL FURTHER NOTICE' in expires_str.upper() or 'UFN' in expires_str.upper() or 'PERM' in expires_str.upper():
        return False

    off = notam_series_offset(notam_id)
    # Try various date formats (case-insensitive month names)
    for fmt in ['%b %d, %Y %H:%M', '%b %d, %Y', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
        try:
            exp_dt = datetime.strptime(expires_str, fmt)
            if 'H' not in fmt:
                exp_dt = exp_dt.replace(hour=23, minute=59)
            exp_dt = exp_dt.replace(tzinfo=timezone.utc) + off
            return now > exp_dt
        except:
            continue

    return False  # Can't parse, assume active

def _notam_time_to_dt(s, is_end, offset=None):
    """Parse a NOTAM effective/expiry string into a timezone-aware UTC datetime.
    offset: series timezone offset (C/K series = -8h)."""
    if not s:
        return None
    off = offset or timedelta(0)
    t = str(s).upper()
    if 'UFN' in t or 'UNTIL FURTHER' in t or 'PERM' in t or '永久' in t:
        return (datetime.max if is_end else datetime.min).replace(tzinfo=timezone.utc)
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?', t)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4) or (23 if is_end else 0)),
                        int(m.group(5) or (59 if is_end else 0)), tzinfo=timezone.utc) + off
    m = re.search(r'([A-Z]{3})\s+(\d{1,2}),?\s*(\d{4})(?:\s+(\d{2}):(\d{2}))?', t)
    if m:
        months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        if m.group(1) in months:
            return datetime(int(m.group(3)), months.index(m.group(1)) + 1, int(m.group(2)),
                            int(m.group(4) or 23), int(m.group(5) or 59), tzinfo=timezone.utc) + off
    return None

def notam_overlaps_flight(notam, fw_start, fw_end):
    """True if the NOTAM validity window overlaps the flight window.
    Missing time info is treated conservatively as overlapping (active)."""
    if fw_start is None or fw_end is None:
        return True
    off = notam_series_offset(notam.get('id'))
    s = _notam_time_to_dt(notam.get('effective') or notam.get('eff_from'), False, off)
    e = _notam_time_to_dt(notam.get('expires'), True, off)
    start = s if s is not None else datetime.min.replace(tzinfo=timezone.utc)
    end = e if e is not None else datetime.max.replace(tzinfo=timezone.utc)
    return start <= fw_end and end >= fw_start

def classify_notam(notam, fw_start=None, fw_end=None):
    """Classify NOTAM into risk level (supports English ICAO + JEP Pro Chinese)."""
    desc = notam['desc'].upper()
    q_code = notam.get('q_code', '').upper()

    # ── 时间相关性: 通告生效窗口与该机场[操作时间-2h, +3h]无交集 → 与本次飞行无关 → LOW ──
    notam['timeIrrelevant'] = False
    if (fw_start is not None and fw_end is not None
            and not notam_overlaps_flight(notam, fw_start, fw_end)):
        notam['timeIrrelevant'] = True
        return 'LOW'

    # ── 最高优先级: 通告明确声明"对起降性能无影响" → 强制 LOW (障碍物/塔吊类) ──
    # 覆盖表格表头 "影响的飞行程序及起飞航径区" 造成的误判
    if re.search(r'NO INFLUENCE ON TAKEOFF AND LANDING PERFORMANCE|NO IMPACT ON TAKE-?OFF', desc) or \
       re.search(r'对起飞和着陆性能(均)?无影响|对起降性能(均)?无影响|对起飞着陆性能(均)?无影响|对性能无影响|无程序影响', desc):
        return 'LOW'

    # MED: runway issues (EN)
    if any(kw in desc for kw in ['RWY CLSD', 'RUNWAY CLOSED', 'RWY DISTANCE REDUCED',
                                   'TORA CHANGED', 'TODA CHANGED', 'ASDA CHANGED', 'LDA CHANGED']):
        return 'MED'
    if re.search(r'\b(?:RWY|RUNWAY)\s+[\dRLC/]+\s+(?:CLSD|CLOSED)', desc):
        return 'MED'
    # MED: runway closure schedule (AIP SUP, e.g. "Scheduled closure of RWY ...")
    if re.search(r'CLOSURE OF RWY|RUNWAY CLOSURE SCHEDULE|SCHEDULED CLOSURE', desc):
        return 'MED'
    # MED: runway closure (CN)
    if '跑道' in desc and ('关闭' in desc or 'CLSD' in desc):
        return 'MED'
    # MED: OEI performance affected
    if '一发失效' in desc or 'ONE ENGINE FAILURE' in desc:
        return 'MED'
    # MED: bird activity / bird strike risk (CN+EN)
    if re.search(r'鸟击|迁徙鸟|候鸟|猛禽|鸟防|驱鸟|BIRD ACTIVITY|BIRD STRIKE|BIRD HAZARD|FLOCK', desc) and '无鸟' not in desc:
        return 'MED'
    # MED: obstacle impacts flight performance / procedures (CN)
    if re.search(r'影响\s*RWY\s*\d+[RL]?.*(?:性能|程序|起飞|一发)', desc):
        return 'MED'
    # 排除表头 "影响的飞行程序及起飞航径区/备注" (非真实影响)
    if re.search(r'影响(?!的飞行程序).*?(?:起飞航径|爬升梯度|进近程序|着陆性能)', desc):
        return 'MED'

    # MED: NAV aids U/S / ON TEST / DO NOT USE (EN+CN) — 归入 MED, 按时间窗口判定
    if re.search(r'VOR/DME|DVOR/DME', desc) and re.search(r'U/S|WITHDRAWN|OUT OF SERVICE|不提供使用|限用|停用', desc):
        return 'MED'
    if re.search(r'\bILS\b|\bDME\b|\bNDB\b|\bVOR\b', desc) and re.search(r'U/S|OUT OF SERVICE|ON TEST|DO NOT USE|不提供使用|停用|测试|禁止使用', desc):
        return 'MED'
    if re.search(r'APCH LGT.*DOWNGRADE|DOWNGRADE TO CAT', desc):
        return 'MED'
    if re.search(r'(SID|STAR|IAC|PROCEDURE).*?(U/S|停用)', desc):
        return 'MED'

    # MED: taxiway full closure (EN)
    if re.search(r'TWY\s+\w+\s+CLSD(?!\s+ONLY|\s+BTN.*ONLY|\s+(?:EAST|WEST|NORTH|SOUTH)\s+OF\b)', desc):
        return 'MED'
    if re.search(r'TWY\s+\w+.*\bCLSD\b', desc) and 'ONLY AVBL' not in desc:
        # 部分关闭(顺序无关): CLSD BTN X AND Y / CLSD EAST OF X / BTN X, TWY Y CLSD
        if re.search(r'(?:BTN|FM|TIL|BETWEEN|(?:EAST|WEST|NORTH|SOUTH)\s+OF)', desc):
            return 'GND CHECK'
        return 'MED'
    # GND CHECK: list-style taxiway/taxilane closures
    # (EN: "TWY CLSD DUE TO WIP DETAIL AS FLW: -TWY K BTN TWY D AND TWY J4 -TWY J3")
    if re.search(r'\b(?:TWY|TXL)\s+CLSD\b', desc):
        return 'GND CHECK'
    # GND CHECK: partial taxiway closure (EN: "THE PARTIAL CLOSURE OF TWY C AND TWY K")
    if re.search(r'(?:PARTIAL\s+)?CLOSURE OF TWY', desc):
        return 'GND CHECK'
    # MED: taxiway closure (CN) — 名称在前 "B滑行道关闭" / "Q11滑道关闭"
    if re.search(r'[A-Z0-9]{1,5}\s*滑行道\s*(?:关闭|不可用|CLSD|停止使用)', desc):
        return 'MED'
    if re.search(r'[A-Z0-9]{1,5}\s*滑\s*(?:关闭|不可用|CLSD)', desc):
        return 'MED'
    # MED: taxiway closure (CN) — "关闭X滑与Y滑之间的Z滑行道/Z滑" = Z整段关闭
    # (与英文 TWY Z CLSD BTN X AND Y → MED 保持一致)
    if re.search(r'关闭.{1,15}滑与.{1,15}滑之间的\s*\S{1,6}滑', desc):
        return 'MED'
    # MED: taxiway closure (CN) — "关闭S1滑行道"
    if re.search(r'关闭\s*\S{1,6}滑行道', desc):
        return 'MED'
    # GND CHECK: taxiway partial closure (CN) — "关闭Q滑以东的J43滑"
    if '关闭' in desc and re.search(r'\S{1,6}滑\b', desc):
        return 'GND CHECK'
    # GND CHECK: intersections closed (EN) — "INT C3, P3 CLSD"
    if re.search(r'\bINT\s+[\w,\s]+CLSD', desc):
        return 'GND CHECK'

    # MED: performance/procedure affecting obstacles with SPECIFIC impact
    perf_patterns = [
        r'TAKE-OFF FLIGHT PATH\s+(?:AREA\s+)?AFFECTED[:\s]*([A-Z0-9]+)',
        r'PROCEDURE\s+AFFECTED[:\s]*([A-Z0-9]+)',
        r'MINIMA\s+CHANGED',
        r'CLIMB\s+GRADIENT',
        r'PENETRATE.*(?:TAKE-OFF|APPROACH|DEPARTURE)\s+PATH',
    ]
    for pat in perf_patterns:
        m = re.search(pat, desc)
        if m:
            if m.lastindex and m.group(1):
                return 'MED'
            elif 'MINIMA CHANGED' in desc or 'CLIMB GRADIENT' in desc:
                return 'MED'

    # GND CHECK: partial taxiway restrictions (EN+CN)
    if any(kw in desc for kw in ['TURN LEFT TO', 'TURN RIGHT TO', 'FORBIDDEN TO TURN',
                                   'FORBIDDEN TO ENTER', 'TURN RESTRICTION',
                                   'FORBIDDEN TO TURN LEFT', 'FORBIDDEN TO TURN RIGHT']):
        return 'GND CHECK'
    if '不得左转' in desc or '不得右转' in desc or '仅限翼展' in desc:
        return 'GND CHECK'
    if re.search(r'右转至\s*\S{1,4}滑\s*仅限', desc):
        return 'GND CHECK'

    # LOW: parking stands (EN+CN)
    if ('PARKING STAND' in desc or 'PRKG STAND' in desc or 'ACFT STAND' in desc) and 'CLSD' in desc:
        return 'LOW'
    if re.search(r'机位关闭', desc):
        return 'LOW'

    # LOW: wingspan limits
    if re.search(r'WING\s*SPAN.*NOT\s*MORE\s*THAN\s*(\d+)', desc):
        limit = int(re.search(r'WING\s*SPAN.*NOT\s*MORE\s*THAN\s*(\d+)', desc).group(1))
        if limit <= 65:
            return 'LOW'

    # LOW: generic obstacles (EN+CN)
    if any(kw in desc for kw in ['OBST', 'CRANE', 'OBSTACLE', 'WIND TURBINE']):
        return 'LOW'
    if '障碍物' in desc or '塔吊' in desc:
        return 'LOW'

    # LOW: generic stand/equipment
    if any(kw in desc for kw in ['PARKING STAND', 'VISUAL DOCKING', 'DEICING', 'PUSHBACK',
                                   '目视停靠', '引导车', 'RAIM']):
        return 'LOW'

    return 'LOW'

def classify_notam_list(notams, fw_start=None, fw_end=None):
    """Classify a list of NOTAMs into categories. Returns structured dict.
    Time-irrelevant NOTAMs (outside the flight window) go to 'folded'."""
    res = {'active': [], 'med': [], 'gnd_check': [], 'low': [], 'folded': []}
    cat_map = {'MED': 'med', 'GND CHECK': 'gnd_check', 'LOW': 'low'}
    for n in notams:
        nn = dict(n)  # 复制一份, 避免把随航班变化的 timeIrrelevant 标志写回 NOTAM 缓存
        cat = classify_notam(nn, None, None)   # 真实等级 (忽略时间窗口)
        nn['cat'] = cat
        time_irr = bool(fw_start is not None and fw_end is not None
                        and not notam_overlaps_flight(nn, fw_start, fw_end))
        nn['timeIrrelevant'] = time_irr
        res['active'].append(nn)
        if time_irr:
            res['folded'].append(nn)           # 不在生效时间范围 → 折叠区
        else:
            res[cat_map[cat]].append(nn)
    return res

def check_notam_future(effective_str, notam_id=None):
    """Check if NOTAM effective date is in the future (not yet active). Series-aware."""
    if not effective_str:
        return False
    off = notam_series_offset(notam_id)
    for fmt in ['%Y-%m-%d %H:%M UTC', '%Y-%m-%d %H:%M']:
        try:
            eff_dt = datetime.strptime(effective_str.strip(), fmt).replace(tzinfo=timezone.utc) + off
            return datetime.now(timezone.utc) < eff_dt
        except:
            continue
    return False

def truncate_text(s, n=150):
    """Collapse whitespace and truncate to n chars (for unrecognized fragments)."""
    t = re.sub(r'\s+', ' ', s).strip()
    return t[:n] + '…' if len(t) > n else t

def parse_jep_notams(text):
    """Parse JEP Pro export format (Chinese/English):
    (**)ZGGG C4537/26 202607171518 - 202610162359 (大约)
    因运行需要,关闭Q滑与Q15滑之间的Q11滑行道.
    Returns ({icao: [notam_dict, ...]}, [unrecognized_fragments])
    """
    result = {}
    unrecognized = []
    header_re = re.compile(
        r'^\(?\*{0,2}\)?\s*([A-Z]{4})\s+([A-Z]\d{3,4}/\d{2})\s+'
        r'(\d{12})\s*-\s*(\d{12}|\(永久\))'
    )
    divider_re = re.compile(r'^(?:-{5,}|\*{4}).*')
    current = None

    def flush():
        nonlocal current
        if current:
            icao, nid, start_s, end_s, desc_lines = current
            desc = re.sub(r'\s+', ' ', ' '.join(desc_lines)).strip()
            if end_s == '(永久)' or (end_s and end_s[:4] == '2999'):
                expires = 'PERMANENT'
            elif end_s:
                expires = f'{end_s[:4]}-{end_s[4:6]}-{end_s[6:8]} {end_s[8:10]}:{end_s[10:12]} UTC'
            else:
                expires = ''
            eff = ''
            if start_s and start_s[:4] not in ('0000',):
                eff = f'{start_s[:4]}-{start_s[4:6]}-{start_s[6:8]} {start_s[8:10]}:{start_s[10:12]} UTC'
            result.setdefault(icao, []).append({
                'id': nid, 'q_code': '', 'priority': '5',
                'effective': eff, 'expires': expires, 'desc': desc,
                'expired': check_notam_expired(expires, nid),
                'not_yet_effective': check_notam_future(eff, nid),
                'manual': True, 'jep': True,
            })
        current = None

    for line in text.split('\n'):
        s = line.strip()
        m = header_re.match(s)
        if m:
            flush()
            current = (m.group(1), m.group(2), m.group(3), m.group(4), [])
        elif divider_re.match(s):
            flush()
        elif current is not None:
            current[4].append(line)
        elif len(re.sub(r'\s', '', s)) > 4:
            unrecognized.append(truncate_text(s, 150))
    flush()
    return result, unrecognized

def _parse_icao_notams(text):
    """Parse ICAO standard format NOTAMs (A)/B)/C)/E) fields).
    Returns ({icao: [notam_dict, ...]}, [unrecognized_fragments])"""
    result = {}
    unrecognized = []
    if not text or not text.strip():
        return result, unrecognized
    blocks = re.split(r'(?=[A-Z]\d{4}/\d{2}\b)', text)
    for block in blocks:
        b = block.strip()
        if not b:
            continue
        m_id = re.match(r'([A-Z]\d{4}/\d{2})', b)
        if not m_id:
            # 无NOTAM编号的片段 → 未识别
            if len(re.sub(r'\s', '', b)) > 4:
                unrecognized.append(truncate_text(b, 200))
            continue
        notam_id = m_id.group(1)

        # 紧凑格式: "A3749/26 WMKK 202610300100-202610300400 描述..."
        m_compact = re.match(
            r'([A-Z]\d{4}/\d{2})\s+([A-Z]{4})\s+(\d{10,12})\s*-\s*(\d{10,12})\b([\s\S]*)', b)
        if m_compact:
            def _fmt_dt(sv):
                if len(sv) == 10:
                    return f'20{sv[:2]}-{sv[2:4]}-{sv[4:6]} {sv[6:8]}:{sv[8:10]} UTC'
                return f'{sv[:4]}-{sv[4:6]}-{sv[6:8]} {sv[8:10]}:{sv[10:12]} UTC'
            c_icao = m_compact.group(2)
            c_eff = _fmt_dt(m_compact.group(3))
            c_exp = _fmt_dt(m_compact.group(4))
            c_desc = re.sub(r'\s+', ' ', m_compact.group(5)).strip()
            result.setdefault(c_icao, []).append({
                'id': notam_id, 'q_code': '', 'priority': '5',
                'effective': c_eff, 'expires': c_exp, 'desc': c_desc,
                'expired': check_notam_expired(c_exp, notam_id),
                'manual': True,
            })
            continue

        m_a = re.search(r'A\)\s*:?\s*([A-Z]{4})\b', b)
        if not m_a:
            unrecognized.append(f'[{notam_id}] 缺少A)机场代码 → ' + truncate_text(b, 150))
            continue
        icao = m_a.group(1)
        # 生效时间: B) 字段 (YYMMDDHHMM)
        effective = ''
        m_b = re.search(r'B\)\s*:?\s*(\d{10})', b)
        if m_b:
            s = m_b.group(1)
            effective = f'20{s[:2]}-{s[2:4]}-{s[4:6]} {s[6:8]}:{s[8:10]} UTC'
        expires = ''
        m_c = re.search(r'C\)\s*:?\s*(\d{10})', b)
        if not m_c:
            m_c = re.search(r'TO\W{0,3}(\d{10})\b', b)
        if m_c:
            s = m_c.group(1)
            expires = f'20{s[:2]}-{s[2:4]}-{s[4:6]} {s[6:8]}:{s[8:10]} UTC'
        else:
            m_to_date = re.search(r'(?:C\)|TO)\W{0,3}(\d{4}-\d{2}-\d{2})', b)
            if m_to_date:
                expires = m_to_date.group(1) + ' 23:59 UTC'
            else:
                m_perm = re.search(r'C\)\s*:?\s*(PERM|UFN)', b, re.IGNORECASE)
                if m_perm:
                    expires = 'PERMANENT'
        m_e = re.search(r'E\)\s*([\s\S]+?)(?=\s*[FGR]\)|$)', b)
        if m_e:
            desc = re.sub(r'\s+', ' ', m_e.group(1)).strip()
        else:
            desc = re.sub(r'\s+', ' ', b).strip()
        m_q = re.search(r'Q\)\s*:?\s*[A-Z]{4}/([A-Z]{5})', b)
        result.setdefault(icao, []).append({
            'id': notam_id,
            'q_code': m_q.group(1) if m_q else '',
            'priority': '5',
            'effective': effective,
            'expires': expires,
            'desc': desc,
            'expired': check_notam_expired(expires, notam_id),
            'manual': True,
        })
    return result, unrecognized

def parse_manual_notams(text):
    """Parse pasted NOTAMs with per-paragraph format routing.
    Each blank-line-separated paragraph is independently detected as
    JEP Pro export or ICAO standard; mixed pastes are supported.
    Returns ({icao: [notam]}, [unrecognized], fmt) where fmt is 'icao' | 'jep' | 'mixed' | 'none'."""
    if not text or not text.strip():
        return {}, [], 'none'
    result = {}
    unrecognized = []
    jep_paras, icao_paras = [], []
    jep_head = re.compile(r'^\(?\*{0,2}\)?\s*[A-Z]{4}\s+[A-Z]\d{3,4}/\d{2}\s+\d{12}\s*-\s*')
    for para in re.split(r'\n\s*\n', text):
        p = para.strip()
        if not p:
            continue
        if any(jep_head.match(ln.strip()) for ln in p.split('\n') if ln.strip()):
            jep_paras.append(p)
        else:
            icao_paras.append(p)
    if jep_paras:
        r1, u1 = parse_jep_notams('\n\n'.join(jep_paras))
        for icao, lst in r1.items():
            result.setdefault(icao, []).extend(lst)
        unrecognized.extend(u1)
    if icao_paras:
        r2, u2 = _parse_icao_notams('\n\n'.join(icao_paras))
        for icao, lst in r2.items():
            result.setdefault(icao, []).extend(lst)
        unrecognized.extend(u2)
    # 完全无法解析的非空文本 → 整体列入未识别
    if not result and not unrecognized and text.strip():
        unrecognized = [truncate_text(text, 300)]
    fmt = 'jep' if jep_paras and not icao_paras else ('mixed' if jep_paras and icao_paras else 'icao')
    return result, unrecognized, fmt

def merge_notam_data(base_nd, manual_list):
    """Merge manual NOTAMs into a NOTAM data dict (same ID overrides)."""
    combined = list(base_nd.get('active', []))
    manual_ids = {n['id'] for n in manual_list}
    combined = [n for n in combined if n['id'] not in manual_ids]
    combined.extend(manual_list)
    return classify_notam_list(combined)

def build_manual_taf(raw_text, target_utc_h, target_utc_m, date_str):
    """Build TAF result dict from manually pasted raw TAF text."""
    raw = raw_text.strip()
    issue = parse_taf_issue(raw)
    valid = parse_taf_valid(raw)
    if not issue or not valid:
        return {'error': 'NO_TAF', 'message': 'TAF格式错误，请粘贴完整TAF(含TAF头)'}
    covers = taf_valid_covers(valid, target_utc_h, target_utc_m, date_str)
    result = {'source': '手动粘贴', 'issue': issue, 'valid': valid, 'covers': covers, 'raw': raw}
    if covers:
        groups = parse_taf_groups(raw)
        result['base'] = groups['BASE']
        result['target_groups'] = []
        result['impact_groups'] = []
        for g_type, g_list in [('TEMPO', groups['TEMPO']), ('BECMG', groups['BECMG']),
                                 ('FM', groups['FM']), ('PROB', groups['PROB'])]:
            for g in g_list:
                exact = taf_target_in_group(valid, g, target_utc_h, target_utc_m, date_str)
                near = taf_target_in_group(valid, g, target_utc_h, target_utc_m, date_str,
                                           WX_WIN_BEFORE, WX_WIN_AFTER)
                if exact:
                    result['target_groups'].append(g)
                elif near:
                    result['impact_groups'].append(g)
        result['risk'] = 'LOW'
        for g in result['target_groups']:
            g_upper = g.upper()
            if any(kw in g_upper for kw in ['TSRA', '+TSRA', 'TS', '+TS', 'CB']):
                result['risk'] = 'HIGH'
            elif any(kw in g_upper for kw in ['SHRA', '+SHRA', 'RA', 'FG', 'BR']):
                if result['risk'] != 'HIGH':
                    result['risk'] = 'MED'
    return result

def _build_opener():
    """Build a urllib opener honoring proxy environment variables."""
    ctx = ssl.create_default_context()
    proxy_url = None
    for var in ['https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY', 'all_proxy', 'ALL_PROXY']:
        val = os.environ.get(var)
        if val:
            proxy_url = val
            break
    if proxy_url:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}),
            urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

def _notam_time_to_expires(s):
    """Convert NOTAM 10-digit UTC time YYMMDDHHMM → 'Mon DD, YYYY HH:MM UTC'."""
    if not s or len(s) < 10 or not s.isdigit():
        return ''
    try:
        dt = datetime(2000 + int(s[0:2]), int(s[2:4]), int(s[4:6]),
                      int(s[6:8]), int(s[8:10]), tzinfo=timezone.utc)
        return dt.strftime('%b %d, %Y %H:%M UTC')
    except Exception:
        return ''

def fetch_notams_faa(icao):
    """Fetch NOTAMs from the FAA NOTAM Search API (covers intl airports).
    Returns a list of normalized NOTAM dicts, or None if the source failed."""
    import urllib.parse
    url = 'https://notams.aim.faa.gov/notamSearch/search'
    body = urllib.parse.urlencode({
        'searchType': '0',
        'designatorsForLocation': icao,
        'notamsOnly': 'false',
        'radius': '10',
        'pageSize': '200',
        'pageNum': '1',
    }).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'),
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': 'https://notams.aim.faa.gov/notamSearch/',
        'Origin': 'https://notams.aim.faa.gov',
    })
    try:
        with _build_opener().open(req, timeout=25) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception:
        return None
    items = data.get('notamList') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None

    out = []
    for it in items:
        raw = it.get('icaoMessage') or it.get('traditionalMessage') or it.get('text') or ''
        nid = it.get('notamNumber') or ''
        q_code = (it.get('qCode') or '').strip().upper()
        eff, exp, desc = '', '', ''
        if raw:
            mq = re.search(r'Q\)\s*[A-Z]{4}/([A-Z]{5})', raw)
            if mq and not q_code:
                q_code = mq.group(1)
            mb = re.search(r'B\)\s*(\d{10})', raw)
            if mb:
                eff = _notam_time_to_expires(mb.group(1))
            mc = re.search(r'C\)\s*(\d{10})', raw)
            if mc:
                exp = _notam_time_to_expires(mc.group(1))
            elif re.search(r'C\)\s*(PERM|UFN)', raw, re.IGNORECASE):
                exp = 'PERMANENT'
            me = re.search(r'E\)\s*([\s\S]+?)(?=\s*[FGR]\)|$)', raw)
            if me:
                desc = re.sub(r'\s+', ' ', me.group(1)).strip()
        if not desc:
            desc = re.sub(r'\s+', ' ', raw).strip()
        if not desc:
            continue
        desc = html.unescape(desc)
        if not nid:
            mid = re.search(r'([A-Z]\d{3,4}/\d{2})', raw)
            nid = mid.group(1) if mid else ''
        out.append({
            'id': nid, 'q_code': q_code, 'priority': '5',
            'effective': eff, 'expires': exp, 'desc': desc,
            'expired': check_notam_expired(exp, nid) if exp else False,
        })
    return out

_notam_file_lock = threading.Lock()

def _notam_cache_path():
    return os.path.join(os.path.dirname(__file__), 'notam_cache.json')

# PWA 静态资源白名单: 请求路径 -> (文件名, MIME)
_STATIC_ASSETS = {
    '/manifest.webmanifest': ('manifest.webmanifest', 'application/manifest+json'),
    '/sw.js': ('sw.js', 'application/javascript'),
    '/icon-192.png': ('icon-192.png', 'image/png'),
    '/icon-512.png': ('icon-512.png', 'image/png'),
    '/icon-512-maskable.png': ('icon-512-maskable.png', 'image/png'),
    '/apple-touch-icon.png': ('apple-touch-icon.png', 'image/png'),
}

def load_notam_fallback(icao):
    """Load NOTAMs from local cache file (fallback when online sources fail)."""
    cache_path = _notam_cache_path()
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, 'r') as f:
            data = json.load(f)
        if icao not in data:
            return None
        notams = data[icao].get('notams', [])
        # Use the same expiry check as main code
        active = []
        for n in notams:
            n['effective'] = n.get('effective') or n.get('eff_from', '')  # 兼容旧缓存键名
            n['expired'] = check_notam_expired(n.get('expires', ''), n.get('id'))
            if not n['expired']:
                active.append(n)
        return active
    except:
        return None

def save_notam_cache(icao, notams):
    """Persist freshly fetched online NOTAMs into notam_cache.json.
    Merges into the existing snapshot so the offline fallback stays warm."""
    if not notams:
        return
    with _notam_file_lock:
        try:
            cache_path = _notam_cache_path()
            data = {}
            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            data[icao] = {
                'fetched_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                'notams': notams,
            }
            tmp = cache_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cache_path)
        except Exception:
            pass

def _embedded_notam_cache_js():
    """Build the JS object literal for app.html's embedded NOTAM_CACHE
    from the current notam_cache.json snapshot."""
    data = {}
    try:
        with open(_notam_cache_path(), 'r') as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}
    slim = {}
    for icao, entry in data.items():
        entry = entry if isinstance(entry, dict) else {}
        rows = []
        for n in entry.get('notams', []):
            rows.append({
                'id': n.get('id', ''),
                'q_code': n.get('q_code', ''),
                'effective': n.get('effective') or n.get('eff_from', ''),
                'expires': n.get('expires', ''),
                'desc': n.get('desc', ''),
            })
        slim[icao] = {'fetched_at': entry.get('fetched_at', ''), 'notams': rows}
    return json.dumps(slim, ensure_ascii=False, separators=(',', ':'))

def render_app_html():
    """Return app.html with its embedded NOTAM_CACHE replaced by the latest
    notam_cache.json snapshot, so a downloaded standalone file carries fresh
    data (browsers opened via file:// cannot call the FAA API directly)."""
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.html')
    with open(app_path, 'r', encoding='utf-8') as f:
        html = f.read()
    new_block = 'const NOTAM_CACHE = ' + _embedded_notam_cache_js() + ';'
    html2, n = re.subn(r'const NOTAM_CACHE\s*=\s*\{.*?\n\};',
                       lambda m: new_block, html, count=1, flags=re.DOTALL)
    return html2 if n else html

def get_notams(icao, force=False):
    """Fetch and classify NOTAMs (with 5-min cache). force=True bypasses cache."""
    now = datetime.now(timezone.utc)
    if not force and icao in _notam_cache:
        cached_time, cached_data = _notam_cache[icao]
        if (now - cached_time).total_seconds() < 300:
            return cached_data

    online_notams = fetch_notams_faa(icao)

    online_ok = False
    all_notams = []

    if online_notams:
        all_notams = online_notams
        online_ok = True

    # Fallback to local cache if online fetch failed
    if not online_ok:
        fallback = load_notam_fallback(icao)
        if fallback:
            all_notams = fallback

    active = [n for n in all_notams if not n.get('expired', False)]

    # Persist fresh FAA data so the offline fallback cache stays up to date
    if online_ok:
        save_notam_cache(icao, active)

    result = {'active': [], 'med': [], 'gnd_check': [], 'low': [], 'folded': []}
    for n in active:
        cat = classify_notam(n)
        result[{'MED': 'med', 'GND CHECK': 'gnd_check', 'LOW': 'low'}[cat]].append(n)
        result['active'].append(n)

    # Warnings
    if not online_ok:
        if active:
            result['source_warning'] = (
                '在线数据源(FAA)不可达，当前显示本地缓存数据。'
                '建议核对JEP Pro / 官方AIS获取最新通告。'
            )
        else:
            result['source_warning'] = '在线数据源(FAA)不可达且无本地缓存，请核对JEP Pro / 官方AIS。'
    else:
        result['source_warning'] = (
            'NOTAM来源：FAA官方NOTAM检索(国际覆盖)，'
            '建议交叉核对JEP Pro / 官方AIS确认完整性。'
        )

    _notam_cache[icao] = (now, result)
    return result

def _cached_icaos():
    """ICAO codes currently present in notam_cache.json."""
    try:
        with open(_notam_cache_path(), 'r') as f:
            data = json.load(f)
        return [k for k in data.keys() if isinstance(k, str) and len(k) == 4]
    except Exception:
        return []

def refresh_notams(icaos):
    """Force re-fetch NOTAMs for given ICAOs, updating notam_cache.json.
    Returns {icao: {ok, active, warning}}."""
    results = {}
    for icao in icaos:
        try:
            r = get_notams(icao, force=True)
            w = r.get('source_warning', '') or ''
            ok = not w.startswith('在线数据源(FAA)不可达')
            results[icao] = {'ok': ok, 'active': len(r.get('active', [])), 'warning': w}
        except Exception as e:
            results[icao] = {'ok': False, 'active': 0, 'warning': f'刷新出错: {str(e)[:120]}'}
    return results

# ── Startup pre-warm ──────────────────────────────────────────────
def prewarm_cache():
    """Pre-fetch NOTAMs for common airports in background."""
    common = ['ZGGG', 'ZSPD', 'ZBAA', 'ZSYW', 'ZGSZ', 'ZUCK', 'ZJHK', 'VHHH', 'WMKK', 'VTBS', 'RJTT', 'RKSI']
    def _warm():
        for icao in common:
            try:
                get_notams(icao)
            except:
                pass
    t = threading.Thread(target=_warm, daemon=True)
    t.start()

# ── Brief assembly (shared by GET/POST) ───────────────────────────
def build_brief(params):
    """Assemble the brief response from a params dict. Returns (dict, http_status)."""
    dep = (params.get('dep') or '').upper()
    arr = (params.get('arr') or '').upper()
    date = params.get('date', '')
    dep_time = params.get('dep_time', '')
    arr_time = params.get('arr_time', '')
    arr_date_in = (params.get('arr_date', '') or '').strip()
    manual_notam_text = params.get('manual_notam', '') or ''
    manual_taf_text = params.get('manual_taf', '') or ''
    notam_mode = params.get('notam_mode', 'merge')   # auto | merge | manual
    taf_mode = params.get('taf_mode', 'auto')        # auto | manual

    if not dep or not arr or not date:
        return {'error': '缺少参数'}, 400

    # Parse times
    dep_h, dep_m = bjt_to_utc(dep_time)
    arr_h, arr_m = bjt_to_utc(arr_time)

    if dep_h is None or arr_h is None:
        return {'error': '时间格式错误'}, 400

    # Calculate arrival date: 优先用户填写的 ARR DATE; 否则跨夜(arr_time<dep_time)记次日
    is_overnight = int(arr_time) < int(dep_time)
    dep_date = datetime.strptime(date, '%Y-%m-%d')
    if arr_date_in:
        arr_date = arr_date_in
    elif is_overnight:
        arr_date = (dep_date + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        arr_date = date

    # 关注时段 (UTC): 该机场操作时间(起飞/落地) 前2h ~ 后3h
    try:
        dep_utc_dt = (dep_date + timedelta(hours=int(dep_time[:2]), minutes=int(dep_time[2:4]))
                      - timedelta(hours=8)).replace(tzinfo=timezone.utc)
        arr_utc_dt = (datetime.strptime(arr_date, '%Y-%m-%d')
                      + timedelta(hours=int(arr_time[:2]), minutes=int(arr_time[2:4]))
                      - timedelta(hours=8)).replace(tzinfo=timezone.utc)
        dep_win = (dep_utc_dt - timedelta(hours=2), dep_utc_dt + timedelta(hours=3))
        arr_win = (arr_utc_dt - timedelta(hours=2), arr_utc_dt + timedelta(hours=3))
    except Exception:
        dep_win = arr_win = (None, None)

    # Compute precise UTC date/hour for TAF (到达场)
    taf_utc_date, taf_utc_h, taf_utc_m = bjt_datetime_to_utc_date(date, arr_time, is_overnight)
    # 出发场TAF目标时刻（起飞不跨日）
    dep_taf_utc_date, dep_taf_utc_h, dep_taf_utc_m = bjt_datetime_to_utc_date(date, dep_time, False)

    result = {
        'dep': dep, 'arr': arr, 'date': date,
        'arr_date': arr_date,
        'dep_time': dep_time, 'arr_time': arr_time,
        'dep_name': (resolve_coords(dep) or ('', '', ''))[2],
        'arr_name': (resolve_coords(arr) or ('', '', ''))[2],
        'dep_coords_ok': resolve_coords(dep) is not None,
        'arr_coords_ok': resolve_coords(arr) is not None,
    }

    # Arrival WX hour wrapping (e.g. 2300 -> next hour 0 next day)
    arr_hour_1 = int(arr_time[:2])
    arr_hour_2 = arr_hour_1 + 1
    arr_date_2 = arr_date
    if arr_hour_2 >= 24:
        arr_hour_2 = 0
        arr_date_2 = (datetime.strptime(arr_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    # Parallel fetch all external data
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}

        # WX tasks
        futures['dep_wx'] = executor.submit(get_wx_cached, dep, date, int(dep_time[:2]))
        futures['arr_wx_1'] = executor.submit(get_wx_cached, arr, arr_date, arr_hour_1)
        futures['arr_wx_2'] = executor.submit(get_wx_cached, arr, arr_date_2, arr_hour_2)
        # TAF — use precise UTC date
        futures['taf'] = executor.submit(get_taf_cached, arr, taf_utc_date, taf_utc_h, taf_utc_m)
        futures['dep_taf'] = executor.submit(get_taf_cached, dep, dep_taf_utc_date, dep_taf_utc_h, dep_taf_utc_m)
        # NOTAM
        futures['dep_notam'] = executor.submit(get_notams, dep)
        futures['arr_notam'] = executor.submit(get_notams, arr)

        # Collect results
        for key, future in futures.items():
            try:
                result[key] = future.result(timeout=60)
            except Exception:
                result[key] = None

    # Process WX for departure
    dep_wx = result.pop('dep_wx', None)
    if dep_wx:
        dep_wx['risk'] = risk_wx(dep_wx['pop'], dep_wx['vis'], dep_wx['wx_code'])
        result['dep_wx'] = dep_wx

    # Process WX for arrival
    arr_wx_1 = result.pop('arr_wx_1', None)
    arr_wx_2 = result.pop('arr_wx_2', None)
    if arr_wx_1 and arr_wx_2:
        arr_wx = {
            'icao': arr,
            'precip_1': arr_wx_1['precip'], 'precip_2': arr_wx_2['precip'],
            'pop_1': arr_wx_1['pop'], 'pop_2': arr_wx_2['pop'],
            'rain_1': arr_wx_1['rain'], 'rain_2': arr_wx_2['rain'],
            'wind_spd_1': arr_wx_1['wind_spd'], 'wind_spd_2': arr_wx_2['wind_spd'],
            'wind_dir_1': arr_wx_1['wind_dir'], 'wind_dir_2': arr_wx_2['wind_dir'],
            'wind_gst_1': arr_wx_1['wind_gst'], 'wind_gst_2': arr_wx_2['wind_gst'],
            'vis_1': arr_wx_1['vis'], 'vis_2': arr_wx_2['vis'],
            'wx_code_1': arr_wx_1['wx_code'], 'wx_code_2': arr_wx_2['wx_code'],
            'wx_name_1': arr_wx_1['wx_name'], 'wx_name_2': arr_wx_2['wx_name'],
        }
        worst_pop = max(arr_wx_1['pop'], arr_wx_2['pop'])
        worst_vis = min(arr_wx_1['vis'], arr_wx_2['vis'])
        worst_code = max(arr_wx_1['wx_code'], arr_wx_2['wx_code'])
        arr_wx['risk'] = risk_wx(worst_pop, worst_vis, worst_code)
        result['arr_wx'] = arr_wx
    elif arr_wx_1:
        arr_wx_1['risk'] = risk_wx(arr_wx_1['pop'], arr_wx_1['vis'], arr_wx_1['wx_code'])
        result['arr_wx'] = arr_wx_1

    # ── Manual paste overrides (JEP Pro / ICAO) ──
    manual_notams, manual_unrecognized, manual_fmt = parse_manual_notams(manual_notam_text)
    result['notam_unrecognized'] = manual_unrecognized

    # TAF override — 粘贴的TAF按其ICAO归属到出发/到达场（缺省归到达场）
    if manual_taf_text.strip():
        m_icao = taf_icao_of(manual_taf_text)
        to_dep = (m_icao == dep and dep != arr)
        t_key = 'dep_taf' if to_dep else 'taf'
        t_args = ((dep_taf_utc_h, dep_taf_utc_m, dep_taf_utc_date)
                  if to_dep else (taf_utc_h, taf_utc_m, taf_utc_date))
        cur = result.get(t_key)
        if taf_mode == 'manual':
            result[t_key] = build_manual_taf(manual_taf_text, *t_args)
            if dep != arr:
                other = 'taf' if to_dep else 'dep_taf'
                result[other] = {'error': 'NO_TAF', 'message': '手动模式：此机场未粘贴TAF'}
        elif taf_mode == 'auto' and ((not cur) or cur.get('error')):
            # Auto mode: manual paste as fallback when online TAF fails
            result[t_key] = build_manual_taf(manual_taf_text, *t_args)

    # NOTAM override
    if notam_mode in ('merge', 'manual'):
        for key, icao in (('dep_notam', dep), ('arr_notam', arr)):
            ml = [n for n in manual_notams.get(icao, [])
                  if not n['expired'] and not n.get('not_yet_effective')]
            base_nd = result.get(key) or {'active': [], 'med': [], 'gnd_check': [], 'low': [], 'folded': []}
            # JEP Pro export is the complete airport set → replace entirely
            ml_is_jep = bool(ml) and all(n.get('jep') for n in ml)
            if notam_mode == 'manual':
                if ml:
                    nd = classify_notam_list(ml)
                    nd['source_warning'] = (f'JEP Pro通告{len(ml)}条(仅以粘贴为准)'
                                             if ml_is_jep else f'手动粘贴{len(ml)}条(仅以粘贴为准)')
                else:
                    nd = {
                        'active': [], 'med': [], 'gnd_check': [], 'low': [], 'folded': [],
                        'source_warning': '手动模式：未粘贴有效NOTAM，请展开粘贴框粘贴JEP Pro通告'}
            else:
                if ml:
                    if ml_is_jep:
                        nd = classify_notam_list(ml)
                        nd['source_warning'] = f'JEP Pro通告{len(ml)}条(整组覆盖在线/缓存数据)'
                    else:
                        nd = merge_notam_data(base_nd, ml)
                        nd['source_warning'] = f'含手动粘贴{len(ml)}条(同号覆盖在线/缓存数据)'
                else:
                    nd = base_nd
            result[key] = nd

    # ── Re-classify all NOTAMs with flight-time awareness ──
    # (get_notams caches per-ICAO without flight time; here we apply the flight window)
    for key in ('dep_notam', 'arr_notam'):
        nd = result.get(key)
        if nd and nd.get('active'):
            fw = dep_win if key == 'dep_notam' else arr_win
            re_nd = classify_notam_list(nd['active'], fw[0], fw[1])
            if nd.get('source_warning'):
                re_nd['source_warning'] = nd['source_warning']
            result[key] = re_nd

    return result, 200

# ══════════════════════════════════════════════════════════════════
#  AI Agent · OpenAI 兼容接口（魔搭 ModelScope / 自定义）· 预取数据 + 单次判读
# ══════════════════════════════════════════════════════════════════
def _load_key_file():
    """从同目录 llm_key.txt 读取 Key（每行一个，忽略空行与 # 注释）。便于本地/服务器免环境变量。"""
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llm_key.txt')
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith('#'):
                    return s
    except Exception:
        pass
    return ''

LLM_ENV_BASE = os.environ.get('LLM_BASE_URL', 'https://api-inference.modelscope.cn/v1')
LLM_ENV_MODEL = os.environ.get('LLM_MODEL', 'deepseek-ai/DeepSeek-V4.1-Flash-1017')
LLM_ENV_KEY = os.environ.get('LLM_API_KEY', '') or _load_key_file()
# 魔搭 Qwen3.5 等混合推理模型默认先输出思维链，耗时且易截断输出；置 1 可关闭
LLM_ENV_NO_THINK = os.environ.get('LLM_NO_THINK', '').lower() in ('1', 'true', 'yes', 'on')
AGENT_NOTAM_LIMIT = 70        # 每机场送入模型的最大通告条数
AGENT_NOTAM_DESC = 240        # 每条 E) 原文截断长度
WX_WIN_BEFORE = 2             # 天气影响窗口：目标时刻前 N 小时
WX_WIN_AFTER = 3              # 天气影响窗口：目标时刻后 N 小时

AGENT_SYSTEM_PROMPT = """你是航空运行方向的 WX / TAF / NOTAM 判读智能体，服务对象是专业航空人员。默认机型按 C 类（B737/A320/C919/C909，翼展 27–36m）。

【工作方式】
1. 起降机场的 WX、TAF、NOTAM 已由系统预取并放在 <DATA> 中，附带规则引擎参考等级、有效期与来源，直接判读，不调用任何工具。
2. 数据缺失、源异常或带 source_warning 时，在 notes 说明，不得编造。
3. 只输出一个 JSON 对象，不要多余文字，不要代码块围栏。

【NOTAM 分级规则】
- HIGH：跑道关闭/缩短、影响落地时段的关键导航设施失效（ILS/VOR/DME）、明确写明影响 RWY 的起飞性能或程序受限。
- MED：跑道相关限制、滑行道/联络道整段关闭、导航设备不可用、鸟类活动、明确写明影响性能的障碍物。
- GND CHECK：仅部分滑行道/联络道关闭或转弯方向受限（BTN/FM/TIL、部分关闭、INT 关闭）。表述要精炼且说明问题，例如「E↔J1 部分转弯方向受限」；你不知道实际滑行路线，不要臆断具体路线。
- CHECK TIME：仅在特定时间窗口生效、且与本次航班时段相关的限制（如夜间关闭、按时段限用），提示机组核对时间。
- LOW：机位/登机口关闭、翼展限制 ≤36m 或 ≤65m、未明写性能影响的障碍物/塔吊/施工/鸟情通报/设备测试等。

【必须遵守】
- 凡对 C 类机型不构成运行影响的（机位关闭、翼展 ≤36m/≤65m、未明写性能影响的障碍物）一律判 LOW，且不要解释「C 类不受影响」这类原因。
- LOW 也必须逐条给中文摘要（≤25 字），不得省略；内容再小也要把要点翻成中文。
- 通告列表每行格式：编号|规则引擎参考等级|生效~失效|E)原文。参考等级仅供对照，与航班时段无关或明显判错时可改判。
- HIGH / MED / GND CHECK / CHECK TIME / LOW 必须逐条输出判读，一条不漏；LOW 也要给中文摘要（≤20 字）。
- summary 必须是中文；禁止复制/截断英文原文充当摘要。确实无法归类的写「xx类通告，详见原文」。
- 通告生效时间与航班时段（起飞前 1h ~ 落地后 3h）无交集、或尚未生效的，不参与风险；必要时在 notes 提一句。
- 中文精简，每条 summary ≤40 字；能删的字都删掉，只保留定位所需信息。
- 摘要规范（必须遵守）：
  · 滑行道区段关闭：写「编号 (端点-端点) 关闭」，只写一次「关闭」，不写「部分关闭 / 段」。例：TWY L CLSD BTN ACFT STAND F32 AND ACFT STAND F34 →「L (F32-F34) 关闭」；TWY E BTN INT TWY K AND INT E2 CLSD →「E (K-E2) 关闭」；TWY N BTN T12 AND T13 →「N (T12-T13) 关闭」。
  · 按方位关闭：写「编号 (参照物 方位) 关闭」。例：TWY V1 CLSD NORTH OF TWY T13 →「V1 (T13 以北) 关闭」；原因原文写明时在末尾加「（运行需要）」或「（施工）」「（维护）」。
  · 整条滑行道/联络道关闭：「S1 关闭」「K 关闭」。
  · 交叉口关闭：INT A1 CLSD →「A1 交叉口关闭」；多个写「A1/A2 交叉口关闭」。
  · 机位（PARKING STAND / PRKG STAND / ACFT STAND / AIRCRAFT STAND）统一写成「停机位」：停机位 GT1/GT2 关闭；区间写「停机位 F32-F34」。
  · 导航设施必须写识别码（VKL、LMN、POU、CEN 等），ILS/LOC 写跑道号，例：「LMN VOR/DME 不工作」「32L ILS 下滑台不工作」。
  · TRIGGER NOTAM / AIP 修订：必须译出「改了什么」，不得只写「触发通告」。例：CHANGES TO WMKP AD 2.10, AD 2.12, AD 2.15 AND ADC/APDC/GMC →「AIP 修订 04/26 生效：WMKP 机场资料 2.10/2.12/2.15、机场图/停机位图/地面活动图更新」。
- 摘要中不得出现 TWY / RWY / INT / CLSD / U/S / BTN / ACFT STAND 等英文词，一律写成中文；机位写「停机位」。
- 不得直接输出英文原文充当摘要，也不得只写「VOR/DME 不工作」这类丢失设施信息的表述。

【TAF / WX】
- 天气影响窗口：目标时刻前 2 小时 ~ 后 3 小时（起飞对照 DEP、落地对照 ARR）；变化组落入该窗口即视为有影响（界面自动加粗），无需在文字里说明「前2h/后3h」或「是否在时段」。
- taf_note 格式：逐机场写成「ICAO 起飞/落地 + 实际风、能见度、云（取自 TAF 原文，不要写 BASE 字样）」；有变化组则直接附原文，不加括号说明，例：
  「WMKK 落地 VRB03KT 9999 FEW018，PROB40 TEMPO 3107/3111 雷雨；ZGGG 起飞 14003MPS 8000 SCT040。」
- 若某机场 TAF 不覆盖目标时刻，直接写「不覆盖起飞/落地时刻」，不要编造天气。
- WX：VIS <800m、TS/雷暴、强降水 → HIGH；中等降水或低能见度 → MED；其余 LOW。
- WX 数据块已给出时，禁止在 notes 里说「WX 数据缺失 / 未获取」；只有对应机场的 WX 块为空才允许提示缺失。

【结论】
- risk 取 HIGH / MED / LOW（这是风险等级，不是放行结论）；不要输出 GO / NO-GO / MONITOR，也不要给出推迟、备降、取消等运行决策，放行与否由机组判断。
- HIGH：存在影响起飞或落地的高风险项（如 WX 低于标准、关键导航失效、跑道关闭）；MED：有需关注项；LOW：无显著风险。
- headline 一句话说明主要风险来源，例如「WMKK 落地时段有 TEMPO 雷雨、能见度 5000m，落地风险高」；不要出现「建议推迟/备降/可正常执行」。
- factors 列关键依据（≤7 条）；同类必须合并，不要一条通告一行：
  · 滑行道关闭合并为一行：「滑行道关闭（S1、N (T12-T13)、Q11 (Q-Q15)、V1 (T13 以北)、J43 (Q 以东)）」
  · 按机场分段：「WMKK：ILS 32L GP 不工作；地面：滑行道关闭（L (STAND F32-F34)、E (K-E1)）」
  · 导航设施合并：「LMN/POU/CEN VOR 失效，多条 SID/STAR 不可用」
  · LOW 项一律不要写进 factors（界面会按机场自动合并），只写 HIGH / MED / GND CHECK / CHECK TIME 的依据。
- actions 只写机组需要核对/确认的动作（≤3 条），不写放行决定。
- factors / actions 必须写成中文结论（如「POU/CEN VOR 失效，多条 SID/STAR 不可用」），禁止只列通告编号。可带 1–2 个关键编号辅助定位。

【输出 JSON 结构】
{
  "conclusion": {"risk": "HIGH|MED|LOW", "headline": "一句话", "factors": ["..."], "actions": ["..."]},
  "notam_judgments": [
    {"id": "A2923/26", "level": "HIGH|MED|GND CHECK|CHECK TIME|LOW", "summary": "中文精简判读"}
  ],
  "taf_note": "TAF 要点（可为空字符串）",
  "wx_note": "WX 要点（可为空字符串）",
  "notes": ["数据缺失/需人工核对等提示"]
}
notam_judgments 必须覆盖输入中的每一条通告（含 LOW），一条不漏；summary 全部用中文。"""

def _llm_cfg(payload):
    llm = payload.get('llm') if isinstance(payload, dict) else None
    llm = llm if isinstance(llm, dict) else {}
    base_url = (llm.get('base_url') or LLM_ENV_BASE).rstrip('/')
    no_think = llm.get('no_think')
    if no_think is None:
        # 魔搭渠道默认关闭思维链，避免混合推理模型 40s+ 延迟与输出截断
        no_think = LLM_ENV_NO_THINK or ('modelscope' in base_url)
    return {
        'base_url': base_url,
        'model': llm.get('model') or LLM_ENV_MODEL,
        'api_key': llm.get('api_key') or LLM_ENV_KEY,
        'no_think': bool(no_think),
    }

def llm_chat(messages, tools, cfg, timeout=120, temperature=0.1, response_format=None, max_tokens=None):
    body = {'model': cfg['model'], 'messages': messages, 'temperature': temperature}
    if max_tokens:
        body['max_tokens'] = max_tokens
    if response_format:
        body['response_format'] = response_format
    if cfg.get('no_think'):
        body['chat_template_kwargs'] = {'enable_thinking': False}
    if tools:
        body['tools'] = tools
        body['tool_choice'] = 'auto'
    req = urllib.request.Request(
        cfg['base_url'] + '/chat/completions',
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + cfg['api_key'],
            'Accept': 'application/json',
        })
    try:
        with _build_opener().open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    except urllib.error.HTTPError as e:
        detail = ''
        try:
            detail = e.read().decode('utf-8', errors='replace')[:300]
        except Exception:
            pass
        raise RuntimeError(f'HTTP {e.code} {detail}')
    except Exception as e:
        raise RuntimeError(str(e)[:200])

def _agent_ctx(params):
    """计算航班信息与目标 UTC 时刻（与 build_brief 一致）。"""
    dep = (params.get('dep') or '').upper()
    arr = (params.get('arr') or '').upper()
    date = params.get('date', '')
    dep_time = params.get('dep_time', '')
    arr_time = params.get('arr_time', '')
    arr_date_in = (params.get('arr_date') or '').strip()
    is_overnight = int(arr_time) < int(dep_time)
    dep_dt = datetime.strptime(date, '%Y-%m-%d')
    if arr_date_in:
        arr_date = arr_date_in
    elif is_overnight:
        arr_date = (dep_dt + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        arr_date = date
    taf_utc_date, taf_h, taf_m = bjt_datetime_to_utc_date(date, arr_time, is_overnight)
    dep_taf_utc_date, dep_taf_h, dep_taf_m = bjt_datetime_to_utc_date(date, dep_time, False)
    return {
        'dep': dep, 'arr': arr, 'date': date, 'arr_date': arr_date,
        'dep_time': dep_time, 'arr_time': arr_time,
        'is_overnight': is_overnight,
        'dep_utc': (datetime.strptime(date, '%Y-%m-%d')
                    + timedelta(hours=int(dep_time[:2]), minutes=int(dep_time[2:4]))
                    - timedelta(hours=8)).strftime('%Y-%m-%d %H:%M UTC'),
        'arr_utc': (datetime.strptime(arr_date, '%Y-%m-%d')
                    + timedelta(hours=int(arr_time[:2]), minutes=int(arr_time[2:4]))
                    - timedelta(hours=8)).strftime('%Y-%m-%d %H:%M UTC'),
        'arr_taf_target': f'{taf_utc_date} {taf_h:02d}:{taf_m:02d} UTC',
        'dep_taf_target': f'{dep_taf_utc_date} {dep_taf_h:02d}:{dep_taf_m:02d} UTC',
        'arr_taf_args': (taf_utc_date, taf_h, taf_m),
        'dep_taf_args': (dep_taf_utc_date, dep_taf_h, dep_taf_m),
    }

def _agent_prefetch(ctx):
    """并行预取起降机场 WX / TAF / NOTAM（与 build_brief 同源、共用缓存）。"""
    dep, arr = ctx['dep'], ctx['arr']
    dep_h = int(ctx['dep_time'][:2])
    arr_h = int(ctx['arr_time'][:2])
    arr_h2 = arr_h + 1
    arr_date2 = ctx['arr_date']
    if arr_h2 >= 24:
        arr_h2 = 0
        arr_date2 = (datetime.strptime(ctx['arr_date'], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    jobs = {
        'dep_notam': (get_notams, (dep,)),
        'arr_notam': (get_notams, (arr,)),
        'dep_wx': (get_wx_cached, (dep, ctx['date'], dep_h)),
        'arr_wx': (get_wx_cached, (arr, ctx['arr_date'], arr_h)),
        'arr_wx2': (get_wx_cached, (arr, arr_date2, arr_h2)),
        'arr_taf': (get_taf_cached, (arr,) + tuple(ctx['arr_taf_args'])),
        'dep_taf': (get_taf_cached, (dep,) + tuple(ctx['dep_taf_args'])),
    }
    out = {}
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {k: ex.submit(fn, *args) for k, (fn, args) in jobs.items()}
        for k, f in futs.items():
            try:
                out[k] = f.result(timeout=40)
            except Exception:
                out[k] = None
    return out

def _agent_wx_line(label, w):
    if not w:
        return f'{label} 无数据'
    gust = f" 阵风{w.get('wind_gst')}kt" if w.get('wind_gst') else ''
    return (f"{label} {w.get('time', '')} 风{w.get('wind_dir')}°/{w.get('wind_spd')}kt{gust} "
            f"能见度{w.get('vis')}m {w.get('wx_name') or ''} "
            f"降水概率{w.get('pop')}% 降水{w.get('precip')}mm")

def _agent_taf_block(icao, t, target):
    if not t:
        return f'【TAF {icao}（目标 {target}）】无数据'
    if t.get('error'):
        return f'【TAF {icao}（目标 {target}）】{t.get("message") or t.get("error")}'
    win = ''
    try:
        dt = datetime.strptime(target, '%Y-%m-%d %H:%M UTC')
        s = dt - timedelta(hours=WX_WIN_BEFORE)
        e = dt + timedelta(hours=WX_WIN_AFTER)
        win = f'；影响窗口 {s:%m-%d %H:%M}~{e:%m-%d %H:%M} UTC'
    except Exception:
        pass
    lines = [f'【TAF {icao}（目标 {target}{win}）】来源 {t.get("source", "")} '
             f'ISSUE {t.get("issue", "")} VALID {t.get("valid", "")} 覆盖目标 {t.get("covers")}']
    tg = t.get('target_groups') or []
    if tg:
        lines.append('覆盖目标时刻的变化组：' + ' | '.join(str(g)[:300] for g in tg))
    ig = t.get('impact_groups') or []
    if ig:
        lines.append('影响窗口内的变化组：' + ' | '.join(str(g)[:300] for g in ig))
    if t.get('base'):
        lines.append('基础天气（TAF 原文）：' + str(t['base'])[:300])
    lines.append('原始报文：' + (t.get('raw') or '')[:600])
    return '\n'.join(lines)

def _agent_notam_block(label, icao, nd):
    if not isinstance(nd, dict):
        return f'【NOTAM {label} {icao}】无数据'
    active = nd.get('active') or []
    warn = nd.get('source_warning') or ''
    head = f'【NOTAM {label} {icao}，{len(active)} 条' + (f'；{warn}' if warn else '') + '】'
    rows = []
    ordered = sorted(active, key=lambda n: classify_notam(dict(n)) == 'LOW')
    for n in ordered[:AGENT_NOTAM_LIMIT]:
        desc = re.sub(r'\s+', ' ', n.get('desc') or '')[:AGENT_NOTAM_DESC]
        rows.append(f"{n.get('id', '')}|{classify_notam(dict(n))}|"
                    f"{(n.get('effective') or n.get('eff_from') or '')[:20]}"
                    f"~{(n.get('expires') or '')[:20]}|{desc}")
    if len(active) > AGENT_NOTAM_LIMIT:
        rows.append(f'（另有 {len(active) - AGENT_NOTAM_LIMIT} 条通告未列出，沿用规则引擎结果）')
    return head + '\n' + '\n'.join(rows)

def _extract_json(text):
    if not text:
        return None
    t = text.strip()
    t = re.sub(r'^```(?:json)?\s*', '', t)
    t = re.sub(r'\s*```$', '', t)
    try:
        return json.loads(t)
    except Exception:
        pass
    i, j = t.find('{'), t.rfind('}')
    if i >= 0 and j > i:
        try:
            return json.loads(t[i:j + 1])
        except Exception:
            return None
    return None

def run_agent(params, cfg):
    """单次往返：服务器并行预取数据 → 一次 LLM 调用输出结构化判读。"""
    ctx = _agent_ctx(params)
    t0 = time.time()
    data = _agent_prefetch(ctx)
    prefetch_ms = int((time.time() - t0) * 1000)

    dep, arr = ctx['dep'], ctx['arr']
    parts = [
        '<DATA>',
        f"【航班】{dep} {ctx['date']} {ctx['dep_time']} BJT → "
        f"{arr} {ctx['arr_date']} {ctx['arr_time']} BJT；机型 C 类（翼展 <36m）",
        f"起飞 {ctx['dep_utc']}；落地 {ctx['arr_utc']}",
        _agent_wx_line(f'【WX {dep} 起飞时段】', data.get('dep_wx')),
        _agent_wx_line(f'【WX {arr} 落地时段】', data.get('arr_wx')),
    ]
    if data.get('arr_wx2'):
        parts.append(_agent_wx_line(f'【WX {arr} 落地后1H】', data.get('arr_wx2')))
    parts.append(_agent_taf_block(arr, data.get('arr_taf'), ctx['arr_taf_target']))
    if dep != arr:
        parts.append(_agent_taf_block(dep, data.get('dep_taf'), ctx['dep_taf_target']))
    parts.append(_agent_notam_block('起飞机场', dep, data.get('dep_notam')))
    parts.append(_agent_notam_block('落地机场', arr, data.get('arr_notam')))
    parts.append('</DATA>')
    user = '\n'.join(parts)

    manual_taf = (params.get('manual_taf') or '').strip()
    manual_notam = (params.get('manual_notam') or '').strip()
    if manual_taf:
        user += f'\n\n【用户粘贴的 TAF 报文（以此为准）】\n{manual_taf[:6000]}'
    if manual_notam:
        user += f'\n\n【用户粘贴的 NOTAM（JEP Pro/官方，优先采用，同号覆盖）】\n{manual_notam[:20000]}'
    user += '\n\n请按规则判读，只输出 JSON。'

    messages = [
        {'role': 'system', 'content': AGENT_SYSTEM_PROMPT},
        {'role': 'user', 'content': user},
    ]
    t1 = time.time()
    try:
        resp = llm_chat(messages, None, cfg, timeout=180, temperature=0,
                        response_format={'type': 'json_object'}, max_tokens=2400)
    except RuntimeError as e:
        # 兼容端点可能不支持 response_format → 去掉后重试一次
        if 'HTTP 400' in str(e) or 'HTTP 422' in str(e):
            resp = llm_chat(messages, None, cfg, timeout=180, temperature=0, max_tokens=2400)
        else:
            raise
    llm_ms = int((time.time() - t1) * 1000)

    u = resp.get('usage') or {}
    usage = {'prompt_tokens': int(u.get('prompt_tokens') or 0),
             'completion_tokens': int(u.get('completion_tokens') or 0)}
    choices = resp.get('choices') or []
    if not choices:
        raise RuntimeError('模型无返回')
    msg = choices[0].get('message') or {}
    ai = _extract_json(msg.get('content') or '')
    if not isinstance(ai, dict):
        raise RuntimeError('AI 输出不是有效 JSON：' + (msg.get('content') or '')[:120])

    def _count(key):
        nd = data.get(key)
        return len(nd.get('active') or []) if isinstance(nd, dict) else 0

    meta = {'prefetch_ms': prefetch_ms, 'llm_ms': llm_ms,
            'notam_count': _count('dep_notam') + _count('arr_notam'),
            'prompt_chars': len(user)}
    return ai, meta, usage

_LEVEL_ALIASES = {
    'HIGH': 'HIGH', 'MED': 'MED', 'MEDIUM': 'MED',
    'GND CHECK': 'GND CHECK', 'GNDCHECK': 'GND CHECK',
    'CHECK TIME': 'CHECK TIME', 'CHECKTIME': 'CHECK TIME',
    'LOW': 'LOW',
}

def _norm_level(v):
    if not v:
        return None
    s = re.sub(r'[\s_]+', ' ', str(v).strip().upper())
    return _LEVEL_ALIASES.get(s) or _LEVEL_ALIASES.get(s.replace(' ', '')) or None

def _cn_summary(s):
    """把模型摘要里残留的英文缩写统一成中文，保证界面只出现中文表述。"""
    s = str(s).strip()
    s = re.sub(r'\bTWY\s+', '滑行道', s)
    s = re.sub(r'\bRWY\s*', '跑道', s)
    s = re.sub(r'\bINT\s+', '交叉口', s)
    s = re.sub(r'\bBTN\s+', '之间', s)
    s = re.sub(r'\bCLSD\b', '关闭', s)
    return s

def apply_ai_judgments(brief, judgments):
    """把 AI 判读结果写回通告并重新分桶。未列出的通告保持规则引擎结果。"""
    jmap = {}
    for j in judgments or []:
        if isinstance(j, dict) and j.get('id'):
            jmap[str(j['id']).strip().upper()] = j
    for key in ('dep_notam', 'arr_notam'):
        nd = brief.get(key)
        if not isinstance(nd, dict):
            continue
        for n in nd.get('active', []):
            j = jmap.get(str(n.get('id') or '').strip().upper())
            if not j:
                continue
            lvl = _norm_level(j.get('level'))
            if lvl:
                n['ai_level'] = lvl
            if j.get('summary'):
                s = _cn_summary(j['summary'])
                # 只接受中文摘要；纯英文（模型照抄原文）直接丢弃，前端回退规则中文摘要
                if re.search(r'[\u4e00-\u9fff]', s):
                    n['ai_summary'] = s
        buckets = {'HIGH': [], 'MED': [], 'GND CHECK': [], 'CHECK TIME': [], 'LOW': []}
        folded = []
        for n in nd.get('active', []):
            lvl = n.get('ai_level') or n.get('cat') or 'LOW'
            if n.get('timeIrrelevant'):
                folded.append(n)   # 不在本次航班时段 → 一律折叠，与 AI 给的等级无关
                continue
            buckets.get(lvl, buckets['LOW']).append(n)
        rebuilt = dict(nd)
        rebuilt['high'] = buckets['HIGH']
        rebuilt['med'] = buckets['MED']
        rebuilt['gnd_check'] = buckets['GND CHECK']
        rebuilt['check_time'] = buckets['CHECK TIME']
        rebuilt['low'] = buckets['LOW']
        rebuilt['folded'] = folded
        brief[key] = rebuilt

def _low_lines(brief):
    """把 LOW 项按机场合并成结论依据（塔吊写处数与高度，机位写处数）。"""
    out = []
    for key, icao in (('dep_notam', brief.get('dep')), ('arr_notam', brief.get('arr'))):
        if not icao:
            continue
        items = (brief.get(key) or {}).get('low') or []
        crane = stands = 0
        heights, others = [], []
        for n in items:
            s = (n.get('ai_summary') or '').strip()
            d = n.get('desc') or ''
            if re.search(r'(塔吊|吊车|起重机|障碍物)', s):
                crane += 1
                h = re.findall(r'(\d{2,3})\s*m', s) or re.findall(r'MAX HGT[^0-9]*(\d{2,3})\s*M', d, re.I)
                heights += h
            elif '停机位' in s:
                stands += 1
            elif s and s not in others:
                others.append(s)
        parts = []
        if crane:
            hh = ''
            if heights:
                nums = sorted(set(int(x) for x in heights))
                hh = f'（{nums[0]}' + (f'–{nums[-1]}' if len(nums) > 1 else '') + 'm）'
            parts.append(f'{crane} 处塔吊障碍物{hh}')
        if stands:
            parts.append(f'{stands} 处停机位关闭')
        merged, aip = [], {}
        for s in others:
            m = re.match(r'(AIP[^：]*[：:])', s)
            if m:
                k, tail = m.group(1), s[len(m.group(1)):].strip()
                if k in aip:
                    if tail not in aip[k]:
                        aip[k].append(tail)
                else:
                    aip[k] = [tail]
                    merged.append(k)
            elif s not in merged:
                merged.append(s)
        for it in merged:
            parts.append(it + '、'.join(aip[it]) if it in aip else it)
        parts = parts[:5]
        if parts:
            out.append(f'{icao}：' + '；'.join(parts))
    return out

def agent_brief(params):
    """AI 智能体模式：先由模型取数判读，再用同一份数据构建展示结构。"""
    if not (params.get('dep') and params.get('arr') and params.get('date')):
        return {'error': '缺少参数'}, 400
    cfg = _llm_cfg(params)
    if not cfg['api_key']:
        return {'error': 'AI 未配置：请在网页设置里填 API Key，或把 Key 写入 llm_key.txt，或设置环境变量 LLM_API_KEY',
                'code': 'AI_NOT_CONFIGURED'}, 400
    t0 = time.time()
    try:
        ai, meta, usage = run_agent(params, cfg)
    except Exception as e:
        return {'error': f'AI 判读失败: {str(e)[:200]}', 'code': 'AI_FAILED'}, 502

    brief, code = build_brief(params)
    if code != 200:
        return brief, code
    apply_ai_judgments(brief, ai.get('notam_judgments') or [])
    # 结论只输出风险等级 HIGH/MED/LOW；兼容模型回退到 GO/NOGO/MONITOR 的旧写法
    concl = ai.get('conclusion') if isinstance(ai.get('conclusion'), dict) else {}
    ai['conclusion'] = concl
    raw_risk = str(concl.get('risk') or '').upper().replace('-', '').replace(' ', '')
    risk_map = {'HIGH': 'HIGH', 'NOGO': 'HIGH', 'MED': 'MED', 'MEDIUM': 'MED',
                'MONITOR': 'MED', 'LOW': 'LOW', 'GO': 'LOW'}
    risk = risk_map.get(raw_risk, 'MED')
    if raw_risk in ('NOGO', 'HIGH'):
        high_cnt = (len((brief.get('dep_notam') or {}).get('high') or [])
                    + len((brief.get('arr_notam') or {}).get('high') or []))
        if high_cnt == 0 and raw_risk == 'NOGO':
            risk = 'MED'
            notes = list(ai.get('notes') or [])
            notes.append('模型给出 NOGO 但无 HIGH 项，已按规则调整为 MED')
            ai['notes'] = notes
    concl['risk'] = risk
    low_lines = _low_lines(brief)
    if low_lines:
        fs = concl.get('factors')
        fs = [str(x) for x in fs] if isinstance(fs, list) else []
        fs = [x for x in fs if '低影响' not in x]
        if len(fs) > 5:
            fs = fs[:5]
        fs += low_lines
        concl['factors'] = fs[:7]
    # WX 实际已获取时，剔除模型误报的「WX 数据缺失」提示
    if brief.get('dep_wx') and brief.get('arr_wx'):
        ns = ai.get('notes')
        if isinstance(ns, list):
            ai['notes'] = [
                n for n in ns
                if not ((('WX' in n) or ('天气' in n)) and any(w in n for w in ('缺失', '未获取', '无法获取', '获取失败')))
            ]
    brief['ai'] = {
        'model': cfg['model'],
        'elapsed_ms': int((time.time() - t0) * 1000),
        'prefetch_ms': meta.get('prefetch_ms', 0),
        'llm_ms': meta.get('llm_ms', 0),
        'notam_count': meta.get('notam_count', 0),
        'prompt_chars': meta.get('prompt_chars', 0),
        'usage': usage,
        'conclusion': ai.get('conclusion') or {},
        'taf_note': ai.get('taf_note') or '',
        'wx_note': ai.get('wx_note') or '',
        'notes': ai.get('notes') or [],
        'judgments': len(ai.get('notam_judgments') or []),
    }
    return brief, 200

# ── HTTP server (stdlib, no external dependencies) ────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = 'AviationBrief/1.0'

    def log_message(self, *args):
        pass  # keep console quiet

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _static_file(self, spec):
        filename, mime = spec
        full = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        try:
            with open(full, 'rb') as f:
                data = f.read()
        except Exception:
            self._json({'error': 'not found'}, 404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        # sw.js 必须每次校验更新，其余静态资源可长缓存
        self.send_header('Cache-Control', 'no-cache' if filename == 'sw.js' else 'public, max-age=86400')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if path in ('/', '/index.html'):
                self._send(200, render_app_html(), 'text/html; charset=utf-8')
            elif path == '/api/ping':
                self._json({'ok': True, 'mode': 'server'})
            elif path == '/api/coords':
                c = resolve_coords((q.get('icao') or '').upper())
                self._json({'lat': c[0], 'lon': c[1], 'name': c[2]} if c
                           else {'lat': None, 'lon': None, 'name': ''})
            elif path == '/api/airports':
                self._json({k: v[2] for k, v in AIRPORTS.items()})
            elif path == '/api/brief':
                res, code = build_brief(q)
                self._json(res, code)
            elif path == '/api/refresh':
                icaos = []
                if q.get('all'):
                    icaos = _cached_icaos()
                else:
                    for key in ('dep', 'arr'):
                        v = (q.get(key) or '').upper()
                        if len(v) == 4 and v not in icaos:
                            icaos.append(v)
                if not icaos:
                    self._json({'results': {}, 'error': '请先填写起降机场，或使用 all=1 刷新全部缓存'}, 400)
                else:
                    self._json({'results': refresh_notams(icaos)})
            elif path in _STATIC_ASSETS:
                self._static_file(_STATIC_ASSETS[path])
            elif path == '/download':
                self._download()
            elif path == '/app.html':
                data = render_app_html().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="app.html"')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._json({'error': 'not found'}, 404)
        except Exception as e:
            self._json({'error': f'服务器内部错误: {str(e)[:200]}'}, 500)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path not in ('/api/brief', '/api/agent', '/api/llm/test'):
                self._json({'error': 'not found'}, 404)
                return
            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if length else b''
            try:
                params = json.loads(raw.decode('utf-8')) if raw else {}
            except Exception:
                params = {}
            if path == '/api/brief':
                res, code = build_brief(params)
            elif path == '/api/agent':
                res, code = agent_brief(params)
            else:
                cfg = _llm_cfg(params)
                if not cfg['api_key']:
                    self._json({'ok': False, 'error': '未填写 API Key（网页设置、llm_key.txt 或 LLM_API_KEY 均可）'}, 400)
                    return
                try:
                    r = llm_chat([{'role': 'user', 'content': '只回复两个字母：OK'}], None, cfg, timeout=45)
                    msg = ((r.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
                    self._json({'ok': True, 'model': cfg['model'], 'reply': msg.strip()[:60]})
                except Exception as e:
                    self._json({'ok': False, 'error': str(e)[:200]}, 502)
                return
            self._json(res, code)
        except Exception as e:
            self._json({'error': f'服务器内部错误: {str(e)[:200]}'}, 500)

    def _download(self):
        buf = io.BytesIO()
        project_dir = os.path.dirname(os.path.abspath(__file__))
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(project_dir):
                dirs[:] = [d for d in dirs if d != '__pycache__' and d != 'templates']
                for fname in files:
                    if fname.endswith('.pyc'):
                        continue
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, os.path.dirname(project_dir))
                    if fname == 'app.html':
                        zf.writestr(arcname, render_app_html())
                        continue
                    zf.write(full, arcname)
                    if fname.endswith(('.command', '.sh', '.bat')):
                        zf.getinfo(arcname).external_attr = 0o755 << 16
        data = buf.getvalue()
        self.send_response(200)
        self.send_header('Content-Type', 'application/zip')
        self.send_header('Content-Disposition', 'attachment; filename="aviation-brief.zip"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    prewarm_cache()
    port = int(os.environ.get('PORT', '8080'))
    print(f'Aviation Briefing server running at http://localhost:{port}  (Ctrl+C to stop)')
    try:
        import socket
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        _lan_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        _lan_ip = '127.0.0.1'
    print(f'  iPad / phone (same Wi-Fi): http://{_lan_ip}:{port}')
    print(f'  In Safari: Share -> Add to Home Screen  (installs as an app)')

    def _open_browser():
        import time
        time.sleep(1.2)
        try:
            import webbrowser
            webbrowser.open(f'http://localhost:{port}')
        except Exception:
            pass
    if not os.environ.get('AVBRIEF_NO_BROWSER'):
        threading.Thread(target=_open_browser, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()