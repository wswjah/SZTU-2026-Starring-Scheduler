"""Pack main.cpp as an ASCII, LF-only submission without changing C++ tokens.

Comments are discarded by a small preprocessing-token lexer. Directives retain
their original token adjacency (notably #define F (x) versus #define F(x)).
Code whitespace is removed only when re-lexing the adjacent tokens is safe;
the complete output is then lexed again and checked against the input tokens.
No identifiers are renamed. UTF-8 strings or identifiers are rejected instead
of being silently damaged. Run --self-test to exercise the lexical boundaries.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re


ATTRIBUTION = (
    "// Based on Misuzu0010/SZTU-2026-data-structure-final-homework; local improvements.\n"
)
LITERAL_PREFIXES = (
    'u8R"', 'uR"', 'UR"', 'LR"', 'R"',
    'u8"', 'u"', 'U"', 'L"', '"', "u8'", "u'", "U'", "L'", "'",
)
PUNCTUATORS = sorted((
    "%:%:", ">>=", "<<=", "->*", "...", "<=>", "::", ".*", "->",
    "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
    "*=", "/=", "%=", "+=", "-=", "&=", "^=", "|=", "##",
    "<:", ":>", "<%", "%>", "%:",
), key=len, reverse=True)
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


@dataclass(frozen=True)
class Token:
    kind: str
    text: str


def splice_lines(source: str) -> str:
    # Translation phase 2 happens before recognition of comments and literals.
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    joined = source.replace("\\\n", "")
    # Raw-string bodies reverse phase-2 splicing. The scheduler does not use
    # this combination; reject it instead of silently altering literal data.
    if joined != source and re.search(r'(?:u8|u|U|L)?R"', joined):
        raise ValueError("Raw strings combined with escaped physical newlines need manual review")
    return joined


def lex(source: str) -> list[Token]:
    """Return whitespace, logical newlines and C++ preprocessing tokens."""
    result: list[Token] = []
    index, length = 0, len(source)
    at_line_start = True
    directive = ""
    while index < length:
        char = source[index]
        if char == "\n":
            result.append(Token("newline", "\n"))
            index += 1
            at_line_start, directive = True, ""
            continue
        if char.isspace():
            end = index + 1
            while end < length and source[end].isspace() and source[end] != "\n":
                end += 1
            result.append(Token("space", " "))
            index = end
            continue
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = length if end < 0 else end
            result.append(Token("space", " "))
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated block comment")
            index = end + 2
            # A multiline block comment is one whitespace unit, including in
            # a directive; do not terminate a #define inside the comment.
            result.append(Token("space", " "))
            continue

        if directive == "header" and char == "<":
            end = source.find(">", index + 1)
            if end < 0 or "\n" in source[index:end]:
                raise ValueError("Unterminated #include header name")
            result.append(Token("header", source[index:end + 1]))
            index, directive, at_line_start = end + 1, "", False
            continue

        prefix = next((value for value in LITERAL_PREFIXES
                       if source.startswith(value, index)), None)
        if prefix is not None:
            end = index + len(prefix)
            if 'R"' in prefix:
                delimiter_end = source.find("(", end)
                if delimiter_end < 0 or delimiter_end - end > 16:
                    raise ValueError("Invalid raw-string delimiter")
                delimiter = source[end:delimiter_end]
                if any(value in delimiter for value in " ()\\\t\r\n"):
                    raise ValueError("Invalid raw-string delimiter")
                terminator = ")" + delimiter + '"'
                final = source.find(terminator, delimiter_end + 1)
                if final < 0:
                    raise ValueError("Unterminated raw string")
                end = final + len(terminator)
            else:
                quote = prefix[-1]
                while end < length:
                    if source[end] == "\\":
                        end += 2
                    elif source[end] == quote:
                        end += 1
                        break
                    elif source[end] == "\n":
                        raise ValueError("Unescaped newline in a string/character literal")
                    else:
                        end += 1
                else:
                    raise ValueError("Unterminated string/character literal")
            suffix = IDENTIFIER.match(source, end)
            if suffix:
                end = suffix.end()
            result.append(Token("literal", source[index:end]))
            index, directive, at_line_start = end, "", False
            continue

        if char.isascii() and (char.isdigit() or
                (char == "." and index + 1 < length and source[index + 1].isdigit())):
            end = index + 1
            while end < length:
                value = source[end]
                if value.isascii() and (value.isalnum() or value in "_.'"):
                    end += 1
                elif value in "+-" and source[end - 1] in "eEpP":
                    end += 1
                else:
                    break
            result.append(Token("number", source[index:end]))
            index, directive, at_line_start = end, "", False
            continue
        identifier = IDENTIFIER.match(source, index)
        if identifier:
            value = identifier.group()
            result.append(Token("identifier", value))
            index = identifier.end()
            directive = ("header" if directive == "name" and
                         value in {"include", "include_next", "import"} else "")
            at_line_start = False
            continue

        # C++'s <:: exception is context-sensitive. Keeping < and :: apart
        # during output additionally prevents a fourth character changing it.
        if (source.startswith("<::", index) and
                (index + 3 == length or source[index + 3] not in ":>")):
            value = "<"
        else:
            value = next((candidate for candidate in PUNCTUATORS
                          if source.startswith(candidate, index)), char)
        result.append(Token("punctuator", value))
        if at_line_start and value in {"#", "%:"}:
            directive = "name"
        else:
            directive = ""
        index += len(value)
        at_line_start = False
    return result


def significant(tokens: list[Token]) -> list[Token]:
    return [token for token in tokens if token.kind not in {"space", "newline"}]


@lru_cache(maxsize=None)
def needs_separator(left: Token, right: Token) -> bool:
    if left.text == "." and right.text == ".":
        return True  # Three isolated dots must not turn into an ellipsis.
    if left.text == "<" and right.text == "::":
        return True
    try:
        return significant(lex(left.text + right.text)) != [left, right]
    except ValueError:
        return True


def pack(source: str, conservative: bool = False) -> str:
    tokens = lex(splice_lines(source))
    if any(token.kind == "identifier" and token.text in {"__LINE__", "__FILE__"}
           for token in tokens):
        raise ValueError("Location-dependent __LINE__/__FILE__ macros need a manual policy")
    output = [ATTRIBUTION]
    code: list[Token] = []
    line: list[Token] = []

    def flush_code() -> None:
        previous = None
        for token in code:
            if previous is not None and (conservative or needs_separator(previous, token)):
                output.append(" ")
            output.append(token.text)
            previous = token
        code.clear()

    def flush_line() -> None:
        content = significant(line)
        if content and content[0].text in {"#", "%:"}:
            flush_code()
            if output[-1] and not output[-1].endswith("\n"):
                output.append("\n")
            # Whitespace in a directive can determine whether a macro is
            # function-like; retain it even where regular code needs none.
            directive = "".join(token.text for token in line).strip()
            output.extend([directive, "\n"])
        else:
            code.extend(content)
        line.clear()

    for token in tokens:
        if token.kind == "newline":
            flush_line()
        else:
            line.append(token)
    flush_line()
    flush_code()
    if not output[-1].endswith("\n"):
        output.append("\n")
    packed = "".join(output)
    try:
        packed.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("Non-ASCII code/literal remains after removing comments") from error
    if significant(lex(packed)) != significant(tokens):
        if not conservative:
            return pack(source, conservative=True)
        raise ValueError("Packing changed preprocessing tokens")
    return packed


def self_test() -> None:
    fixtures = [
        'int a/**/b; // comment\nconst char*s="/* literal */ // literal";\n',
        "auto c='\\''; auto d='\\\\';\n",
        'auto s=R"tag(/* raw */\n// raw\\x)tag";\n',
        '#define F (x)\n#define G(x) x+x\nint y=F;\n',
        '#define X /* multi\nline */ 12\nX\n',
        '#define H(a) a \\\n+  + 1\nint a=H(2);\n',
        '#include <bits/stdc++.h>\n#include <path//to/header.h>\n',
        'int x=a+ +b; int y=a/ *b; auto z=1e-2 + .5;\n',
        'auto x=1e + 2; auto y=a . . . b;\n',
        'vector< ::foo> x; bool y=a < ::b;\n',
        'auto x=u8"abc"; auto y="abc"_tag; auto z=1\'000;\n',
        '// Chinese comment: 中文\nint main(){return 0;}\n',
    ]
    for index, fixture in enumerate(fixtures):
        packed = pack(fixture)
        assert significant(lex(splice_lines(fixture))) == significant(lex(packed)), index
        assert "\r" not in packed and packed.isascii()
    assert "#define F (x)" in pack(fixtures[3])
    assert "#define G(x)" in pack(fixtures[3])
    print(json.dumps({"self_test": "passed", "fixtures": len(fixtures)}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="main.cpp")
    parser.add_argument("--output", default="submit.cpp")
    parser.add_argument("--max-bytes", type=int, default=64000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    source_path, target_path = Path(args.input), Path(args.output)
    if source_path.resolve() == target_path.resolve():
        parser.error("Input and output must differ; the readable source is never overwritten")
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8-sig")
    packed = pack(source).encode("ascii")
    if len(packed) > args.max_bytes:
        parser.error(f"Packed source has {len(packed)} bytes; limit is {args.max_bytes}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(packed)
    print(json.dumps({"input": str(source_path), "output": str(target_path),
        "input_bytes": len(source_bytes), "output_bytes": len(packed),
        "limit_bytes": args.max_bytes, "ascii": True, "lf_only": True,
        "tokens_verified": True, "identifiers_renamed": False,
        "input_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "output_sha256": hashlib.sha256(packed).hexdigest()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
