# -*- coding: utf-8 -*-
"""
解析 chapter 输出 JSON 文件,提取唯一角色并初始化 TTS anchor 列表。

输入文件格式(JSON 数组):
    [
        {"dialog": "...", "role": "角色名", "tts_control": "..."},
        ...
    ]

输出:角色字典列表,每个角色对应一个空的 anchor_name 列表(用于后续挂载 TTS 参考音频),
例如
    [
        {"role": "旁白", "anchor_name": []},
        {"role": "楚環", "anchor_name": []},
        ...
    ]

直接运行:
    python tests/test_parse_roles.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / 'tests' / 'fixtures' / 'chapter_sample_output.txt'
DEFAULT_OUTPUT = ROOT / 'tests' / 'fixtures' / 'chapter_roles.json'


def parse_roles(text: str) -> list[dict]:
    """从 JSON 字符串解析,返回按首次出现顺序排序的唯一角色列表,
    每项为 {"role": str, "anchor_name": []}。"""
    data = json.loads(text)
    if isinstance(data, dict):
        for key in ('dialogs', 'data', 'items', 'result'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]

    if not isinstance(data, list):
        raise ValueError('输入不是合法的 JSON 数组')

    seen: set[str] = set()
    ordered: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role', '')).strip()
        gender = str(item.get('gender', '')).strip()
        if not role or role in seen:
            continue
        seen.add(role)
        ordered.append({'role': role, 'gender': gender, 'anchor_name': []})
    return ordered


def parse_roles_file(path: Path) -> list[dict]:
    text = Path(path).read_text(encoding='utf-8').strip()
    return parse_roles(text)


def main() -> int:
    args = sys.argv[1:]
    input_path = Path(args[0]) if args else DEFAULT_INPUT
    output_path = Path(args[1]) if len(args) > 1 else DEFAULT_OUTPUT

    if not input_path.exists():
        print(f'[ERROR] 输入文件不存在: {input_path}', file=sys.stderr)
        return 1

    roles = parse_roles_file(input_path)
    payload = json.dumps(roles, ensure_ascii=False, indent=2)
    print(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + '\n', encoding='utf-8')
    print(f'\n[saved] {output_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
