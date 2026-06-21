"""供包内部统一调用的 Unicode 字符串过滤和清理工具，主要用于发送给提供商 SDK 之前的文本处理。"""

from __future__ import annotations


def sanitize_surrogates(text: str) -> str:
    """过滤并移除未配对的 Unicode 代理区字符 (surrogates)，规范化有效的字符对。

    说明: TypeScript 端内部处理的是 UTF-16 编码单元，因此一个合法的 surrogate 字符对 (代理对)
    能代表一个超越基本多语言面的合法字符并且必须被保留。虽然 Python 在内部通常已经将其存储为
    原生的单个大 Unicode 标量，但格式错误的非法应用外部输入仍可能包含原生的、未成对的
    代理区保留代码点 (比如处于 D800-DFFF 且无法构成对的单独字符)。此函数主要负责
    主动丢弃这些未配对的无效代理字符，同时将合法的成对代理字符安全地合并转换为其真实的合并标量代码点。

    Args:
        text (str): 潜在含有非法代理区字符的代码或纯文本片段字符串。

    Returns:
        str: 经过净化后保证在不同终端或下游 C++ SDK 中都不会爆编码错误的健壮 Unicode 字符串。
    """
    sanitized: list[str] = []
    index = 0

    while index < len(text):
        code_point = ord(text[index])

        if 0xD800 <= code_point <= 0xDBFF:
            if index + 1 < len(text):
                next_code_point = ord(text[index + 1])
                if 0xDC00 <= next_code_point <= 0xDFFF:
                    combined = (
                        0x10000
                        + ((code_point - 0xD800) << 10)
                        + (next_code_point - 0xDC00)
                    )
                    sanitized.append(chr(combined))
                    index += 2
                    continue

            index += 1
            continue

        if 0xDC00 <= code_point <= 0xDFFF:
            index += 1
            continue

        sanitized.append(text[index])
        index += 1

    return "".join(sanitized)
