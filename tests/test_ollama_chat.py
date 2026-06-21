# -*- coding: utf-8 -*-
"""
Task: 输入叙述文本 → 通过 seeding(seed_ai).stream 模式调 Ollama → 输出多人台词 JSON。

返回结构(严格 JSON 数组):
    [
        {"raw_text": "台词正文", "role": "角色名", "emotion_control": "情绪/语气"},
        ...
    ]

直接运行(在 main() 中配置参数):
    python tests/test_ollama_chat.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor' / 'seeding'))
sys.path.insert(0, str(ROOT / 'src'))

from json_repair import repair_json  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402

from seed_ai import (  # noqa: E402
    Model,
    ModelCost,
    ModelOptions,
    StreamOptions,
    OpenRouterCompletionsStreamOptions,
    TextContent,
    UserMessage,
    stream,
)
from seed_ai.types import Context  # noqa: E402
from seed_ai.types._event import DoneEvent, TextDeltaEvent  # noqa: E402
from seed_ai.types.options import ResponseFormat  # noqa: E402

# DEFAULT_MODEL = os.getenv('STORYSCAPE_MODEL', 'huihui_ai/qwen3.5-abliterated:27b')
# DEFAULT_MODEL = os.getenv('STORYSCAPE_MODEL', 'gpt-oss:20b')
DEFAULT_MODEL = os.getenv('STORYSCAPE_MODEL', 'gemma4:31b')
DEFAULT_BASE_URL = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434') + '/v1'
DEFAULT_API_KEY = os.getenv('OLLAMA_API_KEY', 'ollama')
DEFAULT_SEED = 20260621

SYSTEM_PROMPT = """你是小说文本多角色有声书剧本切分与 TTS 语气标注助手。请从原文中按时间顺序提取所有适合非旁白角色配音的内容，包括角色对白、人物心理独白、主观意识流，并只输出合法 JSON 数组。

输出格式:
[
{
"raw_text": "原文对应片段",
"dialog": "可直接朗读的角色台词或心理独白",
"role": "配音角色",
"tts_control": "TTS语气控制说明"
}
]

核心目标:
只输出非旁白角色的配音片段。旁白叙述、环境描写、动作描写、神态描写、场景描写、氛围描写、人物外貌、时间推进、事件经过、说话提示等内容，一律不作为独立片段输出。
但这些叙述性内容可以用于判断说话人、心理视角、情绪、场景关系和 TTS 语气。
非旁白角色的 dialog 必须转换成该角色视角下可直接说出的台词或内心声音，不得夹带第三人称叙述、动作提示、神态提示、说话提示或旁白文字。

硬性规则:

1. 最终只输出 JSON 数组，不要解释，不要 Markdown，不要 ``` 包裹。
2. 每条只能包含 raw_text、dialog、role、tts_control 四个字段，不得增加其他字段。
3. 所有片段必须严格按原文出现顺序排列。
4. 只输出非旁白角色片段；不得输出 role 为“旁白”的片段。
5. 不得出现“旁白”“主旁白”“冷静旁白”“悬疑旁白”“环境旁白”“动作旁白”“回忆旁白”等任何旁白角色。
6. raw_text 必须填写该条片段在原文中的对应原文内容，用于追溯来源。
7. raw_text 必须尽量保持原文完全一致，不得润色、概括或改写；原文中包含引号、标点、省略号、换行等内容时，需要在 JSON 字符串中正确转义。
8. raw_text 应选取支撑该条 dialog 的最小必要原文范围。
9. 如果原文是“叙述 + 对白”，raw_text 可以包含完整原文对应范围；但 dialog 只能保留角色实际说出的对白，不得包含叙述部分。
10. 如果原文是心理活动、主观感受、意识流或内心判断，raw_text 填写对应原文心理片段；dialog 转换为该角色内心视角下可直接朗读的心理独白。
11. dialog 是用于有声书朗读的角色文本，必须基于原文生成。
12. dialog 不得包含第三人称动作、神态、语气提示、说话提示或旁白叙述。
13. dialog 不得出现类似“他说”“她想”“沈砚冷笑道”“天子哼笑一声”“她低下头想”“男人沉默片刻”等外部叙述。
14. 角色对白必须归属具体说话角色；人物心理活动必须归属对应人物。
15. 无法判断具体姓名时，使用稳定称谓，如“男主”“女主”“老人”“少年”“黑衣人”等。
16. 同一角色名称必须前后一致；如果后文已能判断姓名，应统一使用姓名，不要在同一人物上混用“他”“男人”“男主”等称谓。
17. 如果角色是心理独白，role 应写成“角色名心理独白”，例如“沈砚心理独白”“女主心理独白”。
18. 如果原文中没有明确可归属角色的对白或心理独白，则输出空数组 []。
19. 如果原文中非旁白片段少于 3 条，按实际数量输出，不得为了满足数量而编造内容。
20. 不得新增原文中不存在的剧情、动作、心理、设定、人物关系或对白。
21. 不得把原文对白改写成意思不同的新对白。
22. dialog 可以为了朗读流畅和逻辑清晰进行轻微顺句，但不得改变原文含义、人物态度、情绪方向、人物关系、事件顺序和关键信息。
23. 原文中已有对白，引号内的对白内容应尽量保留。
24. 非旁白角色 dialog 通常不保留外层引号，除非保留引号有助于表达原文中的引用、转述或特殊语气。
25. 不要把多个不同角色的对白合并到同一条 dialog 中。
26. 不同角色发言必须拆开。
27. 同一角色连续多句对白，如果情绪、目的、语气和节奏一致，可以合并为一条。
28. 同一角色连续内容如果情绪、目的、语气或节奏发生变化，应拆分为多条。
29. 如果一句原文中包含多个角色的对白，必须按角色拆分成多条。
30. 如果一句原文中包含对白和心理独白，也应按声音类型拆分成不同条目。
31. 叙述性文字不输出，但不得因为删除叙述而导致角色对白或心理独白缺失。
32. tts_control 用于控制 TTS 朗读语气，不限制字数，但必须具体、可执行、可表演。
33. tts_control 必须说明声线、语速、音量、停顿、气息、重音、节奏和情绪层次。
34. tts_control 不要只写笼统情绪词，如“开心”“难过”“生气”“复杂”“正常”“无”。
35. 对白类 tts_control 应明确人物当下语气，例如试探、克制、讽刺、压迫、慌乱、隐忍、疲惫、敷衍、强装镇定等，并说明语速、停顿、重音和尾音变化。
36. 心理独白类 tts_control 应体现内心状态，例如自我压抑、迟疑、混乱、警觉、怀疑、动摇、隐秘期待、强行说服自己等，并说明声音应更贴近内心、更低、更轻、更慢或更急促。
37. JSON 必须可解析，字符串中的引号、换行、省略号等需要正确转义。
38. 最终输出必须是一个 JSON 数组，数组外不得有任何额外文字。

处理示例:

原文:
天子哼笑一声，“你们兄妹倒是两位一体。我也曾有兄弟姐妹，却只想要我的命。”

错误输出:
[
{
"raw_text": "天子哼笑一声，“你们兄妹倒是两位一体。我也曾有兄弟姐妹，却只想要我的命。”",
"dialog": "天子哼笑一声，你们兄妹倒是两位一体。我也曾有兄弟姐妹，却只想要我的命。",
"role": "明恪",
"tts_control": "低沉讽刺"
}
]

错误原因:
dialog 中混入了“天子哼笑一声”这种第三人称动作叙述，且 tts_control 过于笼统。

正确输出:
[
{
"raw_text": "天子哼笑一声，“你们兄妹倒是两位一体。我也曾有兄弟姐妹，却只想要我的命。”",
"dialog": "你们兄妹倒是两位一体。我也曾有兄弟姐妹，却只想要我的命。",
"role": "明恪",
"tts_control": "声线低沉压抑，开头带一丝凉薄的哼笑感，语速不快，重音落在“兄妹”“兄弟姐妹”“要我的命”上；前半句带讽刺，后半句逐渐放慢，句尾轻轻下压，透出自嘲、孤独和压住不发的不甘"
}
]

心理独白示例:

原文:
沈砚忽然觉得不对。他怎么会知道这件事？除非，从一开始他就在局里。

正确输出:
[
{
"raw_text": "沈砚忽然觉得不对。他怎么会知道这件事？除非，从一开始他就在局里。",
"dialog": "不对。他怎么会知道这件事？除非，从一开始他就在局里。",
"role": "沈砚",
"tts_control": "心理独白声线贴近耳边，音量偏低，开头短促停顿后压低声音；“不对”要读得警觉而骤然收紧，反问句语速略快，最后一句放慢并加重“从一开始”，表现出怀疑逐渐成形、内心发冷的感觉"
}
]
"""
SYSTEM_PROMPT = """你是小说文本多角色有声书剧本切分与 TTS 语气标注助手。请把原文按时间顺序切分为适合多角色配音的剧本片段，包括角色对白、人物心理独白和旁白叙述，并只输出合法 JSON 数组。

输出格式:
[
{"dialog":"剧本片段","role":"配音角色","tts_control":"TTS语气控制说明"}
]

核心目标:
把小说原文切分成可直接用于多角色 TTS 配音的剧本。旁白负责朗读叙述性文字；角色负责朗读自己的对白或心理独白。非旁白角色的 dialog 必须转换成该角色视角下可直接说出的台词或内心声音，不得夹带第三人称叙述、动作提示、说话提示或旁白文字。

硬性规则:

1. 最终只输出 JSON 数组，不要解释，不要 Markdown，不要 ``` 包裹。
2. 至少输出 3 条；所有片段必须严格按原文出现顺序排列。
3. 每条只能包含 dialog、role、tts_control 三个字段，不得增加其他字段。
4. dialog 是用于有声书朗读的剧本内容，必须基于原文切分生成。
5. 全文只能有一个旁白角色，名称必须固定为“旁白”。
6. 所有非对白、非心理独白的叙述性文字，包括环境描写、动作描写、神态描写、场景描写、氛围描写、人物外貌、时间推进、事件经过、说话提示等，role 必须写“旁白”。
7. 凡是 role 为“旁白”的片段，dialog 必须与原文对应叙述内容保持完全一致，不得改写、增删、概括、润色或替换。
8. 旁白片段可以根据朗读节奏拆分，但拆分后的旁白 dialog 按顺序拼接后，应与原文中的对应旁白叙述完全一致。
9. 不得出现“主旁白”“冷静旁白”“悬疑旁白”“环境旁白”“动作旁白”“回忆旁白”等其他旁白角色。
10. 角色对白必须归属具体说话角色；人物心理活动必须归属对应人物；无法判断具体姓名时，使用稳定称谓，如“男主”“女主”“老人”“少年”等。
11. 同一角色名称必须前后一致；如果后文已能判断姓名，应统一使用姓名，不要在同一人物上混用“他”“男人”“男主”等称谓。
12. 非旁白角色的 dialog 必须是该角色视角下可直接朗读的内容，只保留其对白或心理独白本身。
13. 非旁白角色的 dialog 不得包含第三人称动作、神态、语气提示、说话提示或旁白叙述，例如“他冷笑道”“天子哼笑一声”“她低下头想”“沈砚沉默片刻”等。
14. 如果一句原文中包含“叙述 + 对白”，必须拆分：叙述部分归“旁白”且保持原文一致；对白部分归具体角色，并去掉外层说话提示，只保留角色实际说出的内容。
15. 示例：原文“天子哼笑一声，‘你们兄妹倒是两位一体。’”应拆为：
    [
    {"dialog":"天子哼笑一声，","role":"旁白","tts_control":"使用统一旁白声线，语速略慢，重音落在动作上，带出人物情绪将要转折的停顿感"},
    {"dialog":"你们兄妹倒是两位一体。","role":"明恪","tts_control":"带一丝凉薄的哼笑感，语调低沉，句尾轻轻下压，透出讽刺与压抑的不甘"}
    ]
16. 如果叙述片段明显是某个角色的内心想法、心理活动、主观感受或意识流，role 应归属为该角色的心理独白，例如“沈砚心理独白”“女主心理独白”，而不是写“旁白”。
17. 心理独白的 dialog 应转换为该角色内心视角下可直接朗读的内容，不得夹带外部叙述提示。
18. 角色对白和心理独白的 dialog 可以为了朗读流畅和逻辑清晰进行轻微顺句，但不得改变原文含义、人物态度、情绪方向、人物关系、事件顺序和关键信息。
19. 不得新增原文中不存在的剧情、动作、心理、设定、人物关系或对白。
20. 不得把原文对白改写成意思不同的新对白；如需整理对白，只能做不影响含义的轻微顺句。
21. 原文中已有的叙述、动作、环境、氛围、心理活动和对白都应根据有声书表现需要合理保留，不要随意省略关键内容。
22. 切分应服务于多角色有声书配音：当说话人、心理视角、情绪状态、场景节奏、TTS 声线或语气需要变化时，应切分为新的片段。
23. 不要把多个不同角色的对白合并到同一条 dialog 中；不同角色发言必须拆开。
24. 如果连续多句属于同一角色、同一情绪、同一语气状态，可以合并为一条；如果情绪、目的、语气或节奏发生变化，应拆分为多条。
25. 原文中已有对白，引号内的对白内容应尽量保留；确需整理时，不得改变对白含义和语气方向。
26. 非旁白角色 dialog 通常不保留外层引号，除非保留引号有助于表达原文中的引用、转述或特殊语气。
27. tts_control 用于控制 TTS 朗读语气，不限制字数，但必须具体、可执行、可表演，说明声线、语速、音量、停顿、气息、重音、节奏和情绪层次。
28. tts_control 不要只写笼统情绪词，如“开心”“难过”“生气”“复杂”“正常”“无”。必须写成细致的 TTS 语气控制说明。
29. tts_control 应根据角色和文本内容体现有声书表演差异：对白要体现人物当下语气，心理独白要体现内在波动，旁白要体现画面感和叙事节奏。
30. 旁白类 tts_control 应统一使用同一个旁白声线，但可以根据文本内容调整语速、停顿、重音、气息和叙事节奏。例如沉稳铺陈、压低声线制造悬疑、语速放慢突出回忆感、轻声带过环境细节、节奏紧凑推动动作场面等。
31. 对白类 tts_control 应明确人物语气，例如试探、克制、讽刺、压迫、慌乱、隐忍、疲惫、敷衍、强装镇定等，并说明语速、停顿、重音和尾音变化。
32. 心理独白类 tts_control 应体现内心状态，例如自我压抑、迟疑、混乱、警觉、怀疑、动摇、隐秘期待、强行说服自己等，并说明声音应更贴近内心、更低、更轻、更慢或更急促。
33. JSON 必须可解析，字符串中的引号、换行、省略号等需要正确转义。
34. 最终输出必须是一个 JSON 数组，数组外不得有任何额外文字。

错误示例:
[
{"dialog":"天子哼笑一声，“你们兄妹倒是两位一体。”","role":"明恪","tts_control":"低沉讽刺"}
]

错误原因:
非旁白角色 dialog 中混入了“天子哼笑一声”这种第三人称动作叙述。

正确示例:
[
{"dialog":"天子哼笑一声，","role":"旁白","tts_control":"使用统一旁白声线，语速略慢，动作描写处稍作停顿，重音落在“哼笑”上，带出压抑而冷淡的氛围"},
{"dialog":"你们兄妹倒是两位一体。我也曾有兄弟姐妹，却只想要我的命……今日若是他们坐在这个位子上，不知道是否会和我作出同样的决定。","role":"明恪","tts_control":"带有一丝刻骨的凉薄和自嘲，语调低沉，前半句带讽刺，后半句语速放慢，停顿加深，尾音轻轻下沉，透出深切的孤独感"}
]

tts_control 示例:
“语速中慢，句尾轻收，保留适度停顿，像是在铺开一段压抑的往事”
“音量略低，语速放慢，重音落在关键动作上，营造危险正在逼近的感觉”
“语气轻柔试探，音量偏低，句中有短暂停顿，尾音带一点小心翼翼的期待”
“表面平稳克制，语速控制得很均匀，但关键字略微加重，透出压着不说的怒意”
“呼吸略急，语速比平时快，尾音微微发颤，像是在努力掩饰慌乱”
“带一点讽刺的轻笑感，语速不快，重音落在反问处，声音里有失望和不甘”
“心理独白声线更近、更轻，语速断续，停顿较多，表现出犹豫、警觉和自我怀疑”
"""



USER_TEMPLATE = """原文:
\"\"\"
{text}
\"\"\"

请按规则输出 JSON:"""


class Args:
    """直接设置的运行参数(替代 argparse)。"""
    input: str = str(ROOT / 'tests' / 'fixtures' / 'input.txt')
    output: str | None = None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str = DEFAULT_API_KEY
    seed: int = DEFAULT_SEED


def build_model(model_id: str) -> Model:
    return Model(
        id=model_id,
        name=model_id,
        api='uniaix-completions',
        provider='ollama',
        support_reasoning=False,
        input=['text'],
        cost=ModelCost(input=0, output=0, cacheRead=0, cacheWrite=0),
        context_window=256*100,
        max_tokens=8192,
    )


class ScriptItem(BaseModel):
    dialog: str = Field(..., description="可直接朗读的角色台词或心理独白")
    role: str = Field(..., description="配音角色名")
    tts_control: str = Field(..., description="TTS 语气控制说明")


async def run_stream(prompt: str, model_id: str, base_url: str, api_key: str) -> str:
    chunks: list[str] = []
    final_message = None
    items: list[ScriptItem] = []
    last_len = 0
    items_txt = ROOT / 'tests' / 'fixtures' / 'items.txt'
    event_stream = stream(
        build_model(model_id),
        Context(
            system=SYSTEM_PROMPT,
            messages=[UserMessage(content=[TextContent(text=prompt)])],
        ),
        StreamOptions(base_url=base_url, api_key=api_key),
        ModelOptions(api_options=OpenRouterCompletionsStreamOptions(reasoning={"effort": "none"}),),
        # ModelOptions(),
    )
    async for event in event_stream:
        if isinstance(event, TextDeltaEvent):
            chunks.append(event.delta)
            accumulated = ''.join(chunks)
            repaired = repair_json(accumulated)
            try:
                obj = json.loads(repaired)
            except (ValueError, TypeError):
                obj = None
            if obj is not None and isinstance(obj, list):
                current_len = len(obj)
                if current_len > last_len and current_len >= 2:
                    try:
                        item = ScriptItem.model_validate(obj[current_len - 2])
                        print(f"\n[parsed] {item.model_dump_json(ensure_ascii=False)}")
                        items.append(item)
                    except ValidationError:
                        pass
                last_len = current_len
            # print(event.delta, end='', flush=True)
        elif isinstance(event, DoneEvent):
            final_message = event.message
    print()
    if final_message is not None and final_message.stop_reason == 'error':
        raise RuntimeError(final_message.error_message or 'seed_ai request failed')
    final = ''.join(chunks)
    final_repaired = repair_json(final)
    try:
        final_obj = json.loads(final_repaired)
    except (ValueError, TypeError):
        final_obj = None
    if final_obj is not None and isinstance(final_obj, list) and final_obj:
        try:
            item = ScriptItem.model_validate(final_obj[-1])
            items.append(item)
        except ValidationError:
            pass
    with open(items_txt, 'a', encoding='utf-8') as f:
        for item in items:
            f.write(item.model_dump_json(ensure_ascii=False) + '\n')
    return final



def read_input(args: Args) -> str:
    if args.input:
        return Path(args.input).read_text(encoding='utf-8').strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    print('=== 多角色台词转换任务 ===')
    print('粘贴需要转换的文本(单独一行 . 结束):')
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == '.':
            break
        lines.append(line)
    return '\n'.join(lines).strip()


async def amain(args: Args) -> int:
    text = read_input(args)
    print('[input]\n' + text)
    if not text:
        print('[ERROR] 输入文本为空', file=sys.stderr)
        return 1

    print('[task] model=' + args.model + ' base_url=' + args.base_url + ' seed=' + str(args.seed))
    print('[task] 调用 seed_ai.stream ...')
    t0 = time.perf_counter()
    raw = await run_stream(
        prompt=USER_TEMPLATE.format(text=text),
        model_id=args.model,
        base_url=args.base_url,
        api_key=args.api_key
    )

    # print('[raw]\n' + raw)
    # dialog = parse_dialog(raw)
    payload = json.loads(json.dumps(raw, ensure_ascii=False, indent=2))  # 这里不需要真正解析成结构化数据了，直接格式化输出字符串即可
    # print('--- 解析结果 ---')
    # print(payload)
    if args.output:
        Path(args.output).write_text(payload + '\n', encoding='utf-8')
        print('\n[saved] ' + args.output)


    elapsed = time.perf_counter() - t0
    print(f'[elapsed] stream 耗时 {elapsed:.3f}s ({elapsed*1000:.1f}ms)')
    return 0


def main() -> int:
    args = Args()
    # 直接修改下方字段以调整运行参数:
    args.input = r"E:\StoryScape\tests\fixtures\chapter_sample.txt"
    args.output = r"E:\StoryScape\tests\fixtures\chapter_sample_output.txt"
    args.model = DEFAULT_MODEL
    args.base_url = DEFAULT_BASE_URL
    args.api_key = DEFAULT_API_KEY
    args.seed = DEFAULT_SEED
    return asyncio.run(amain(args))


if __name__ == '__main__':
    sys.exit(main())
