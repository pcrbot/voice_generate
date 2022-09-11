import asyncio
import hashlib
import json
import random
import re
import time
import traceback

import httpx
import websockets
from aiocqhttp import MessageSegment
from nonebot import CommandSession

import hoshino

fn_index = [
    {
        "index": 1,
        "character": ["綾地寧々", "因幡めぐる", "朝武芳乃", "ムラサメ", "鞍馬小春", "在原七海"],
        "accept_language": ["ja"],
        "title": "サノバウィッチ & 千恋＊万花 & RIDDLE JOKER",
    },
    {
        "index": 5,
        "character": ["和泉妃愛", "常盤華乃", "錦あすみ", "鎌倉詩桜", "竜閑天梨", "和泉里", "新川広夢", "聖莉々子"],
        "accept_language": ["ja"],
        "title": "喫茶（カフェ）ステラと死神の蝶",
    },
    {
        "index": 13,
        "character": ["春日野穹", "天女目瑛", "依媛奈緒", "渚一葉"],
        "accept_language": ["ja"],
        "title": "ヨスガノソラ",
    },
    {
        "index": 17,
        "character": ["蓮華", "篝ノ霧枝", "沢渡雫", "亜璃子", "灯露椎", "覡夕莉"],
        "accept_language": ["ja"],
        "title": "美少女万華鏡",
    },
    {
        "index": 21,
        "character": ["綾地寧々", "在原七海", "小茸", "唐乐吟"],
        "accept_language": ["ja", "zh-CN"],
        "title": "綾地寧々+在原七海+小茸+唐乐吟",
    },
    {
        "index": 29,
        "character": [
            "鷹倉杏璃",
            "鷹倉杏鈴",
            "アペイリア",
            "倉科明日香",
            "ATRI",
            "アイラ",
            "新堂彩音",
            "姫野星奏",
            "小鞠ゆい",
            "聖代橋氷織",
            "有坂真白",
            "白咲美絵瑠",
            "二階堂真紅",
        ],
        "accept_language": ["ja"],
        "title": "Galgame 13 characters",
    },
    {
        "index": 9,
        "character": [
            "四季ナツメ",
            "明月栞那",
            "墨染希",
            "火打谷愛衣",
            "汐山涼音",
        ],
        "accept_language": ["ja"],
        "title": "ハミダシクリエイティブ",
    },
]

help_text = ""

sv = hoshino.Service("合成语音", bundle="pcr娱乐", help_=help_text)

search_japanese = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")


async def get_voice(model_index: int, text: str, character: str, speed: int = 1):
    try:
        async with websockets.connect(
            "wss://spaces.huggingface.tech/skytnt/moe-tts/queue/join"
        ) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "fn_index": model_index,
                        "data": [text, character, speed, False],
                    }
                )
            )
            while True:
                recv_msg = await websocket.recv()
                try:
                    recv_json = json.loads(recv_msg)
                    print(recv_json)
                except Exception as e:
                    traceback.print_exc()
                    continue
                if recv_json.get("msg") == "estimation":
                    if recv_json.get("queue_eta") != 0:
                        process_eta = recv_json.get("rank_eta") + recv_json.get(
                            "queue_eta"
                        )
                        await asyncio.sleep(int(recv_json.get("queue_eta")))
                elif recv_json.get("msg") == "process_completed":
                    if not recv_json.get("success"):
                        return False
                    file_name = (recv_json.get("output", {}).get("data", []))[1].get(
                        "name"
                    )
                    return f"https://hf.space/embed/skytnt/moe-tts/file={file_name}"
    except Exception as e:
        traceback.print_exc()


async def translate(text):
    lts = str(int(time.time() * 1000))
    salt = lts + str(random.randint(0, 9))
    sign_str = "fanyideskweb" + text + salt + "Ygy_4c=r#e#4EX^NUGUc5"
    m = hashlib.md5()
    m.update(sign_str.encode())
    sign = m.hexdigest()
    url = "https://fanyi.youdao.com/translate_o?smartresult=dict&smartresult=rule"
    headers = {
        "Referer": "https://fanyi.youdao.com/",
        "Cookie": "OUTFOX_SEARCH_USER_ID=-1124603977@10.108.162.139; JSESSIONID=aaamH0NjhkDAeAV9d28-x; OUTFOX_SEARCH_USER_ID_NCOO=1827884489.6445506; fanyi-ad-id=305426; fanyi-ad-closed=1; ___rl__test__cookies=1649216072438",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
    }
    data = {
        "i": text,
        "from": "zh-CHS",
        "to": "ja",
        "smartresult": "dict",
        "client": "fanyideskweb",
        "salt": salt,
        "sign": sign,
        "lts": lts,
        "bv": "a0d7903aeead729d96af5ac89c04d48e",
        "doctype": "json",
        "version": "2.1",
        "keyfrom": "fanyi.web",
        "action": "FY_BY_REALTlME",
    }
    res = httpx.post(url, headers=headers, data=data)
    response = json.loads(res.text)
    value = response["translateResult"][0][0]["tgt"]
    return value


async def text_process(text: str, model_index: int) -> str:
    support_chinese = "zh-CN" in fn_index[model_index]["accept_language"]
    if not support_chinese:
        if search_japanese.search(text):
            return text
        text = await translate(text)
    return text


@sv.on_command("合成语音")
async def _get_voice(session: CommandSession):
    args = session.current_arg.split()
    if len(args) != 2:
        session.finish(
            "请输入合成语音 作品序号+角色序号 文本（中日文皆可）\n" "例如【美少女万華鏡】中的【蓮華】请输入“合成语音 40 こんにちは。”\n"
        )
    char = args[0]
    text = args[1]
    if not char.isdigit():
        session.finish(
            "请输入合成语音 作品序号+角色序号 文本（中日文皆可）\n" "例如【美少女万華鏡】中的【蓮華】请输入“合成语音 40 こんにちは。”\n"
        )
    title_index = int(str(char)[0]) - 1
    char_index = int(str(char)[1:])
    try:
        char_name = fn_index[title_index]["character"][char_index]
        internal_index = fn_index[title_index]["index"]
        print(char_name)
    except Exception as e:
        session.finish("角色或作品不存在哟，请检查输入~")
    session.finish(
        MessageSegment.record(
            await get_voice(
                internal_index, await text_process(text, title_index), char_name
            )
        )
    )


@sv.on_command("合成语音帮助")
async def _get_voice(session: CommandSession):
    await session.finish(help_text)


def generate_help():
    global help_text
    help_text = (
        "===语音合成使用指南===\n"
        "请输入合成语音 作品序号+角色序号 文本（中日文皆可）\n"
        "例如【美少女万華鏡】中的【蓮華】请输入“合成语音 40 こんにちは。”\n"
    )
    n = 1
    for i in fn_index:
        a = 1
        help_text += f"【{n}】.【{i.get('title')}】\n"
        for k, v in enumerate(i.get("character")):
            if a >= 4 or k + 1 == len(i.get("character")):
                help_text += f"{k}.{v}\n"
                a = 1
            else:
                help_text += f"{k}.{v} "
                a += 1
        n += 1


generate_help()
