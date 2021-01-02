import config
import argparse
import re
import hashlib
import datetime
import math
from collections import OrderedDict

parser = argparse.ArgumentParser(description="Cool #drive-in thing")
parser.add_argument("--srt", action="store_true", help="Save as srt instead of ass")
parser.add_argument("--no-srt-pos", action="store_true", help="Disable positioning for srt subtitles")
parser.add_argument("--intermission", type=int, default=600, help="Duration of intermission")
parser.add_argument("viewing", type=int, nargs="?")

args = parser.parse_args()

log_formats = {
    "hexchat": {
        "ignore": r"^\w{3,4}\.?\s[0-9]+\s[0-9:]{8}\s\*\s+(?:Now talking on #|Topic for #)",
        "split": r"^\*\*\*\* BEGIN LOGGING AT ",
        "said": r"^\w{3,4}\.?\s[0-9]+\s[0-9:]{8}\s<(?P<nickname>[A-Za-z_-\|0-9]+)>\s(?P<words>.+)",
        "join/part/quit": r"^\w{3,4}\.?\s[0-9]+\s[0-9:]{8}\s\*\s+(?P<nickname>[A-Za-z_-\|0-9]+)\s(?:\([^)]+\) )has (?P<action>(?P<join>joined)|(?P<part>left)|(?P<quit>quit))(?:\s\((?P<reason>.+)\))?",
        "action": r"^\w{3,4}\.?\s[0-9]+\s[0-9:]{8}\s\*\s+(?P<nickname>[A-Za-z_-\|0-9]+)\s(?P<words>.+)",
        "notice": r"^\w{3,4}\.?\s[0-9]+\s[0-9:]{8}\s-(?P<nickname>[A-Za-z_-\|0-9]+)(?:\/#(?P<source>.+?))?-\s(?P<words>.+)",
        "time": r"^\w{3,4}\.?\s[0-9]+\s(?P<hours>[0-9]{2}):(?P<minutes>[0-9]{2}):(?P<seconds>[0-9]{2})"
    }
}

announce = r"^(?P<day>[^:]*?MONDAY[^:]*|[^:]*?TUESDAY[^:]*|[^:]*?WEDNESDAY[^:]*|[^:]*?THURSDAY[^:]*|[^:]*?FRIDAY[^:]*|[^:]*?SATURDAY[^:]*|[^:]*?SUNDAY[^:]*): (?P<title>.+?)(?: \[(?P<year>\d+)\] (?:by (?P<director>.+?)|// (?P<comment>.+?) // (?P<date>.+?)))? \/\/ (?P<ptp>https:\/\/passthepopcorn\.me\/.*?) \/\/ Picked by (?P<nickname>.+?) \/\/ Viewing starts at (?P<abstime>.+?) according.+?\((?P<reltime>[^)]+) until next viewing\)\s*\/\/ Run by (?P<honcho>.+)"
starting = r"10 SECONDS UNTIL (?!RESUMATION|INTERMISSION)(?P<title>.+?)(?: \[(?P<year>\d+)\] BY (?P<director>.+))?$"
rating = r'^\s?(?P<rating>[^/]+)\/10 ["“”](?P<quote>.+)["“”]'

def parse_line(line, log_format):
    time = re.search(log_formats[log_format]["time"], line)
    if not time:
        timedict = {}
        time = None
    else:
        timedict = time.groupdict()
        time = time.group(0)
    match = None
    role = None
    for title, regex in log_formats[log_format].items():
        if title == "time":
            continue
        match = re.search(regex, line)
        if match:
            if title == "ignore":
                return None
            role = title
            break
    if match:
        return {"role": role, "time": time, **dict(map(lambda x: (x[0], int(x[1] or "0")), timedict.items())), **match.groupdict()}
    return None

def parse_logs(file, log_format):
    logs = []
    with open(file) as f:
        lines = f.readlines()
        for line in lines:
            parsed = parse_line(line, log_format)
            if parsed:
                logs.append(parsed)
    return logs

def rgbify(nickname):
    return hashlib.md5(nickname.strip("+@~_<>-* 	").encode()).hexdigest()[:6]

def to_seconds(hours, minutes, seconds):
    return hours * 3600 + minutes * 60 + seconds

def time_between(a, b):
    hdiff = b["hours"] - a["hours"]
    if a["hours"] > b["hours"]:
        hdiff = 24 + b["hours"] - a["hours"]
    mdiff = b["minutes"] - a["minutes"]
    sdiff = b["seconds"] - a["seconds"]
    return hdiff * 3600 + mdiff * 60 + sdiff

def srt_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{int(hours):02}:{int(minutes):02}:{math.floor(seconds):02},{f'{seconds:.3f}'[-3:]}"

def ass_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{int(hours)}:{int(minutes):02}:{math.floor(seconds):02}.{f'{seconds:.2f}'[-2:]}"

def rgb_bgr(rgb):
    return f"{rgb[-2:]}{rgb[-4:-2]}{rgb[-6:-4]}"

def alpha_to_hex(alpha):
    return f"{int(255 * alpha / 100):02x}".upper()

def build_subs(lines, pick, start, movie_file=None):
    offset = 0
    last = start
    last_end = 0
    quotes = None
    ratings_please = None
    out = f"""
[Script Info]
; #drive-in - Synchronised IRC movie viewings
; {pick['ptp']}
Title: #drive-in - {pick['title']}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 720
PlayResY: 480

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: #drive-in,Open Sans,22,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,90,100,0,0,1,1.5,1,8,30,30,14,1
Style: IRC,Syntax LT,23,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,90,100,0,0,1,0,1.5,2,20,20,18,1
Style: Quotes,Segoe Print,30,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,8,10,10,10,1
Style: Stars,Wingdings,90,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,2

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if args.srt:
        out = ""
    i = 0
    top = r"{\an8}"
    middle = r"{\an5}"
    if args.no_srt_pos:
        top = middle = ""
    for line in lines:
        if ratings_please and time_between(ratings_please, line) > 3600:
            break
        if line["role"] == "notice" and line["nickname"] == "Snackbot":
            if line["words"] in ["INTERMISSION! RESUME IN 10 MINUTES", "RESUME IN 10 MINUTES"]:
                offset += args.intermission
        time = to_seconds(line["hours"], line["minutes"], line["seconds"]) + offset
        line["start"] = time_between(start, line) - 10 - offset
        if line.get("nickname", "") in ["Snackbot", pick["honcho"]]:
            if quotes is None and line["words"].strip(".") in ['!starthelper', 'RATINGS AND QUOTES, PLEASE', 'PLEASE GIVE ME YOUR QUOTES AS FOLLOWS x/10 "quote"', 'PLEASE GIVE ME YOUR SCORES AND QUOTES AS FOLLOW x/10 "quote"', 'PLEASE GIVE ME YOUR SCORES AND QUOTES AS FOLLOWS x/10 "quote"', 'PLEASE GIVE ME YOUR SCORES AND QUTOES AS FOLLOWS x/10 "quote"']:
                quotes = {}
                ratings_please = line
                last_end = line["start"]
        last = line
        if ratings_please:
            rated = re.search(rating, line.get("words", ""))
            if rated:
                quotes[line["nickname"]] = rated.groupdict()
        elif line.get("nickname", "") not in ["Snackbot", "NickServ"]:
            if "words" not in line:
                continue
            info = {"alpha": None}
            if line["start"] == int(last_end) or line["start"] == int(last_end)+1:
                line["start"] = last_end
            last_end = line["start"] + min(15, max(2, len(line["words"])*14/100))
            if line.get("nickname", "") == "Hummingbird":
                info["alpha"] = 80
            i += 1
            if args.srt:
                out += f"{i}\n{srt_time(line['start'])} --> {srt_time(last_end)}\n{top}<font color=\"#{rgb_bgr(rgbify(line['nickname']))}\">{line['nickname']}</font>: {line['words']}\n\n"
            else:
                out += f"Dialogue: 0,{ass_time(line['start'])},{ass_time(last_end)}"+r",#drive-in,,0,0,0,,{\4c&H"+rgbify(line["nickname"])+"&}<"+line["nickname"]+r">{\rIRC} "+line["words"]+"\n"
    for nickname, info in quotes.items():
        if args.srt:
            out += f"{i}\n{srt_time(last_end)} --> {srt_time(last_end+5)}\n{middle}<font color=\"#{rgb_bgr(rgbify(nickname))}\">{nickname}</font>\n{info['rating']}/10\n“<i>{info['quote']}</i> ”\n\n"
        else:
            out += f"Dialogue: 0,{ass_time(last_end)},{ass_time(last_end+5)}"+r",#drive-in,,0,0,0,,{\4c&H"+rgbify(line["nickname"])+"&}<"+line["nickname"]+r">{\rIRC}\N"+info["rating"]+r"/10\N{\rQuotes}“{\i1}"+info["quote"]+r"{\i0}"+"”\n"
        last_end += 5
        i += 1
    if args.srt:
        out += f"{i}\n{srt_time(last_end+5)} --> {srt_time(last_end+15)}\n{top}<i>Join us in #drive-in</i>"
    else:
        out += f"Dialogue: 0,{ass_time(last_end+5)},{ass_time(last_end+15)}"+r",#drive-in,,0,0,0,,{\i1}Join us in #drive-in"
    print(out.strip())

def index(lines, single=None):
    picks = OrderedDict()
    for line in lines:
        if "words" in line and line["nickname"] == "Snackbot":
            pick = re.search(announce, line["words"])
            if pick:
                info = pick.groupdict()
                picks[pick["title"]] = {**line, **info}
    if single:
        for i, (_, pick) in enumerate(picks.items()):
            if i+1 == single:
                return pick
        return None
    return picks

def show_index(lines):
    for i, (_, pick) in enumerate(picks.items()):
        print(i+1, f"{pick['title']}{' ('+pick['year']+')' if pick['year'] else ''}")

lines = parse_logs(config.log_file, config.log_format)

if not args.viewing:
    picks = index(lines)
    show_index(lines)
    exit()

pick = index(lines, args.viewing)
if not pick:
    exit("Invalid viewing")

title = f"{pick['title'].upper()}{' ('+pick['year']+')' if pick['year'] else ''}"

start = None
viewing_lines = []

for line in lines:
    if start:
        if line["role"] == "split":
            break
        viewing_lines.append(line)
    if line["role"] == "notice" and line["nickname"] == "Snackbot":
        in10 = re.search(starting, line["words"])
        if not in10:
            continue
        if start:
            break
        info = in10.groupdict()
        if f"{info['title'].upper()}{' ('+info['year']+')' if info['year'] else ''}" == title:
            start = line

if not viewing_lines:
    exit(f"Could not find lines for {pick['title']}{' ('+pick['year']+')' if pick['year'] else ''}")

build_subs(viewing_lines, pick, start)
