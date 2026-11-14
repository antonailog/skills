"""Conservative shell text analysis. Never executes commands or expands variables."""
import ast
import glob
import os
import re
import shlex
import warnings
from pathlib import Path


READERS = {"cat", "head", "tail", "sed", "grep", "rg", "awk", "nl", "less"}
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "bash", "sh", "zsh"}
WRITES = re.compile(r"\b(?:write_text|write_bytes|writeFile(?:Sync)?|appendFile(?:Sync)?|save|imwrite|screenshot)\s*\(|\bopen\s*\([^\n]*?['\"][wax][b+]?['\"]")
# 数字参数（15.5、0.75）不是文件名
FILE_LITERAL = re.compile(r"^(?![+-]?\d+(?:\.\d+)+$)[^\n\r\x00<>|;{}]+\.[a-zA-Z0-9_-]{1,12}$")


def path_of(token, cwd):
    if not token or any(x in token for x in ("$", "`", "\x00", "\n")) or token.startswith(("http://", "https://")):
        return None
    p = os.path.expanduser(token)
    return os.path.realpath(os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd or os.getcwd(), p)))


def expand_known(token, variables):
    """Only literal assignments and the known cwd; never evaluate shell code."""
    return re.sub(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)", lambda m: variables.get(m[1] or m[2], m[0]), token)


def heredocs(command):
    """Remove bodies while keeping a marker on each owning shell command."""
    lines = command.splitlines(keepends=True)
    clean, bodies = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        pattern = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][\w]*)\2")
        matches, markers = list(pattern.finditer(line)), []

        def mark(match):
            marker = "__trace_heredoc_%d__" % (len(bodies) + len(markers))
            while marker in command:
                marker += "_"
            markers.append(marker)
            return " " + marker + " "

        clean.append(pattern.sub(mark, line))
        i += 1
        for m, marker in zip(matches, markers):
            body = []
            while i < len(lines) and lines[i].strip() != m[3]:
                body.append(lines[i].lstrip("\t") if m[1] else lines[i])
                i += 1
            i += 1
            bodies.append({"header": line, "body": "".join(body), "marker": marker, "literal": bool(m[2]), "redirection": m[0]})
    return "".join(clean), bodies


def segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    # `2>/dev/null` lexes as `2`, `>`, `/dev/null`. A digit written right before < or > is a file
    # descriptor, not an argument; drop it so every parser sees a plain redirection.
    fds = set(re.findall(r"(?:^|[\s;|&(])(\d+)(?=[<>])", command))
    tokens = [t for i, t in enumerate(tokens)
              if not (t in fds and i + 1 < len(tokens) and re.fullmatch(r"[<>]+&?", tokens[i + 1]))]
    result, part = [], []
    for token in tokens:
        if token and all(c in ";&|\n" for c in token):
            if part:
                result.append((part, token))
            part = []
        else:
            part.append(token)
    if part:
        result.append((part, ""))
    return result


def raw_segments(command):
    """Find shell boundaries without reformatting quotes or redirections."""
    result, start, i, quote, depth = [], 0, 0, None, 0
    substitutions, backtick_quotes = [], []
    while i < len(command):
        char = command[i]
        if char == '\\' and quote != "'":
            i += 2
            continue
        if quote != "'" and quote != '`' and command[i:i + 2] == '$(':
            substitutions.append((depth, quote))
            depth, quote, i = depth + 1, None, i + 2
            continue
        if char == '`' and quote in (None, '"'):
            backtick_quotes.append(quote)
            quote = '`'
            i += 1
            continue
        if quote:
            if char == quote:
                quote = backtick_quotes.pop() if quote == '`' else None
            i += 1
            continue
        if char in ('"', "'", '`'):
            quote = char
        elif char == '#' and (i == 0 or command[i - 1].isspace()):
            end = command.find('\n', i)
            if depth:
                i = end + 1 if end >= 0 else len(command)
                continue
            if command[start:i].strip():
                result.append((command[start:i].strip(), '\n'))
            if end < 0:
                return result
            start, i = end + 1, end + 1
            continue
        elif char == '(':
            depth += 1
        elif char == ')':
            depth = max(0, depth - 1)
            if substitutions and depth == substitutions[-1][0]:
                _, quote = substitutions.pop()
        elif char in ';\n|&' and not depth:
            # & is also part of 2>&1 and &>/dev/null, not a command boundary.
            if char == '&' and ((i and command[i - 1] in '<>') or command[i:i + 2] == '&>'):
                i += 1
                continue
            end = i + 1
            while end < len(command) and command[end] in ';\n|&':
                end += 1
            if command[start:i].strip():
                result.append((command[start:i].strip(), command[i:end]))
            start, i = end, end
            continue
        i += 1
    if command[start:].strip():
        result.append((command[start:].strip(), ''))
    return result


def command_parts(command):
    """Simple commands, with control words unwrapped and original spelling."""
    clean, bodies = heredocs(command)
    result, loop_headers = [], []
    for raw, separator in raw_segments(clean):
        control = re.match(r'^(for|select|case)\b', raw)
        if control:
            if control[1] in ('for', 'select'):
                loop_headers.append(raw)
            # Substitutions in a loop header may do real work; do not silently
            # call that a listing-only command.
            if '$(' in raw or '`' in raw:
                result.append(dict(raw=raw, display_raw=loop_headers[0] if loop_headers else raw,
                                   tokens=[control[1]], bodies=[], control=True))
            continue
        raw = re.sub(r'^(?:(?:do|then|else|elif|if|while|until)\s+)+', '', raw)
        if re.fullmatch(r'(?:done|fi|esac|do|then|else)', raw):
            if raw == 'done' and loop_headers:
                loop_headers.pop()
            continue
        # A substitution is one shell word. Never strip just `d=$(ffprobe`
        # and mistake its -v argument for the command's beginning.
        if '$(' not in raw and '`' not in raw:
            raw = re.sub(r'^(?:[A-Za-z_]\w*=(?:"(?:\\.|[^"\\])*"|\'(?:[^\']*)\'|[^\s]+)\s*)+', '', raw)
        parsed = segments(raw)
        if not parsed:
            continue
        tokens = parsed[0][0]
        owned = [b for b in bodies if b['marker'] in tokens]
        tokens = [t for t in tokens if not t.startswith('__trace_heredoc_')]
        if not tokens:
            continue
        for body in owned:
            raw = re.sub(' ' + re.escape(body['marker']) + r'(?: |$)', lambda _: body['redirection'], raw)
        result.append(dict(raw=raw, display_raw=loop_headers[0] if loop_headers else raw,
                           tokens=tokens, bodies=owned, separator=separator, control=False))
    return result


def file_only_python(body):
    """File edits plus ordinary string computation need no extra Exec row."""
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return False
    allowed = {'Path', 'open', 'read', 'read_text', 'read_bytes', 'readlines', 'write', 'write_text', 'write_bytes',
               'writelines', 'close', 'replace', 'sub', 'subn', 'split', 'splitlines', 'join', 'strip', 'rstrip', 'lstrip',
               'find', 'index', 'rfind', 'count', 'startswith', 'endswith', 'format', 'len', 'str', 'int', 'list',
               'dict', 'set', 'range', 'enumerate', 'print', 'mkdir', 'makedirs', 'exists', 'resolve', 'expanduser',
               'dumps', 'loads', 'get', 'escape', 'search', 'match', 'compile', 'group', 'append', 'extend', 'insert'}
    file_io = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            root = node.func
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in ('requests', 'httpx', 'subprocess', 'socket', 'urllib'):
                return False
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
            if name not in allowed:
                return False
            file_io = file_io or name in {'open', 'read', 'read_text', 'read_bytes', 'readlines', 'write', 'write_text', 'write_bytes', 'writelines'}
    return file_io


def activities(command, cwd):
    """Classify the work inside a Bash call, independent of result timing."""
    result = []
    for part in command_parts(command):
        tokens = part['tokens']
        name, args = os.path.basename(tokens[0]), tokens[1:]
        if name == 'cd' or (name == 'mkdir' and '-p' in args):
            continue
        kind = 'exec'
        if part['control'] or '$(' in part['raw'] or '`' in part['raw']:
            pass
        elif name == 'ls':
            kind = 'list'
        elif name in ('echo', 'printf', 'true', 'false', ':', 'test', '[', '[['):
            kind = 'aux'
        elif name in ('tee', 'cp', 'mv', 'touch'):
            kind = 'write'
        elif name in ('cut', 'sort', 'uniq', 'wc', 'tr', 'find'):
            kind = 'read'
        elif name in READERS:
            if name == 'sed' and any(a.startswith(('-i', '--in-place')) for a in args):
                kind = 'write'
            elif name == 'cat' and part['bodies'] and any(a in ('>', '>>') for a in args):
                kind = 'write'
            else:
                kind = 'read'
        elif re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', name):
            bodies = [b['body'] for b in part['bodies']]
            if '-c' in args and args.index('-c') + 1 < len(args):
                bodies.append(args[args.index('-c') + 1])
            if bodies and all(file_only_python(body) for body in bodies):
                kind = 'write' if any(inline_paths(body, cwd) for body in bodies) else 'read'
        result.append(dict(part, kind=kind))
    return result


def reader_args(name, args):
    values = {"head": {"-n", "-c", "--lines", "--bytes"},
              "tail": {"-n", "-c", "--lines", "--bytes", "--pid", "--sleep-interval"},
              "grep": {"-A", "-B", "-C", "-m", "-e", "-f", "--after-context", "--before-context", "--context", "--max-count", "--regexp", "--file", "--include", "--exclude"},
              "rg": {"-A", "-B", "-C", "-m", "-e", "-f", "-g", "--glob", "--type", "--max-count"},
              "sed": {"-e", "-f", "--expression", "--file"},
              "awk": {"-F", "-v", "-f"},
              "nl": {"-b", "-d", "-f", "-h", "-i", "-l", "-n", "-s", "-v", "-w"},
              "less": {"-P", "-p", "-x", "-y", "-z"}}.get(name, set())
    positional, options, scripts = [], {}, []
    i, literal, has_pattern = 0, False, False
    while i < len(args):
        a = args[i]
        if name == 'sed' and (a == '-i' or a.startswith('-i') or a.startswith('--in-place')):
            # BSD accepts `-i ''`; GNU's bare -i must not eat the script.
            options['-i'] = a[2:] or True
            if a == '-i' and i + 1 < len(args) and (args[i + 1] == '' or re.fullmatch(r'\.[\w.-]+', args[i + 1])):
                i += 1
            i += 1
            continue
        # The tokenizer splits `2>/dev/null` into `2`, `>`, `/dev/null`; the digit is a file descriptor, not an argument.
        if re.fullmatch(r"\d+", a) and i + 1 < len(args) and args[i + 1] in (">", ">>", "<", ">&", "<&"):
            i += 1
            continue
        if a in (">", ">>", "<", "<<", ">&", "<&", "&>", "&>>", "2>", "2>>"):
            i += 2
            continue
        if a == "--" and not literal:
            literal = True
            i += 1
            continue
        if not literal and a.startswith("-") and a != "-":
            key, eq, value = a.partition("=")
            if key in values:
                if not eq:
                    i += 1
                    value = args[i] if i < len(args) else ""
                options[key] = value
                if key in ("-e", "-f", "--expression", "--regexp", "--file"):
                    has_pattern = True
                    scripts.append(value)
            else:
                attached = next((k for k in values if k.startswith("-") and not k.startswith("--") and a.startswith(k) and len(a) > len(k)), None)
                if attached:
                    options[attached] = a[len(attached):]
                    if attached in ("-e", "-f"):
                        has_pattern = True
                        scripts.append(a[len(attached):])
                else:
                    options[a] = True
            i += 1
            continue
        if name in {"sed", "grep", "rg", "awk"} and not has_pattern:
            scripts.append(a)
            has_pattern = True
        elif a != "-":
            positional.append(a)
        i += 1
    coverage = {"kind": "full", "label": "全文", "selectors": []}
    if name in {"head", "tail"}:
        byte_count = options.get("-c", options.get("--bytes"))
        lines = options.get("-n", options.get("--lines", next((k[1:] for k in options if k[1:].isdigit()), "10")))
        coverage = {"kind": "partial", "label": name + (" " + str(byte_count) + " 字节" if byte_count is not None else " " + str(lines) + " 行"), "selectors": [{"method": name, "bytes": byte_count, "lines": None if byte_count else lines}]}
    elif name == "sed":
        ranges = [[int(a), int(b or a)] for script in scripts for a, b in re.findall(r"(?:^|;)\s*(\d+)(?:,(\d+))?p\b", script)]
        coverage = {"kind": "partial", "label": "sed " + ("、".join("第 %s–%s 行" % tuple(r) for r in ranges) if ranges else "筛选或变换"), "selectors": [{"method": "sed", "ranges": ranges, "scripts": scripts}]}
    elif name in {"grep", "rg", "awk"}:
        coverage = {"kind": "partial", "label": name + " 筛选", "selectors": [{"method": name, "scripts": scripts}]}
    return positional, coverage, options


def inline_paths(body, cwd):
    if not WRITES.search(body):
        return []
    literals = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(body)
        env = {}

        def evaluate(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.Name):
                return env.get(node.id)
            if isinstance(node, ast.BinOp):
                left, right = evaluate(node.left), evaluate(node.right)
                if left is not None and right is not None:
                    return os.path.join(left, right) if isinstance(node.op, ast.Div) else left + right if isinstance(node.op, ast.Add) else None
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                values = [evaluate(a) for a in node.args]
                if name in ("Path", "str", "expanduser", "abspath", "resolve") and values and values[0] is not None:
                    return values[0]
                if name == "join" and values and all(v is not None for v in values):
                    return os.path.join(*values)
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value = evaluate(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Name) and value is not None:
                        env[target.id] = value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            target = None
            if name in ("write_text", "write_bytes", "save", "screenshot") and isinstance(node.func, ast.Attribute):
                target = evaluate(node.func.value) if name.startswith("write_") else evaluate(node.args[0]) if node.args else None
                if name == "screenshot":
                    target = next((evaluate(k.value) for k in node.keywords if k.arg == "path"), target)
            elif name == "open":
                mode = evaluate(node.args[1]) if len(node.args) > 1 else next((evaluate(k.value) for k in node.keywords if k.arg == "mode"), "r")
                if mode and any(c in mode for c in "wax"):
                    target = evaluate(node.args[0]) if node.args else None
            elif name in ("writeFile", "writeFileSync", "appendFile", "appendFileSync", "imwrite") and node.args:
                target = evaluate(node.args[0])
            if target:
                literals.append(target)
    except SyntaxError:
        # JavaScript: static named bindings and direct path arguments only.
        env = dict(re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*['\"]([^'\"\n]+)['\"]", body))
        for m in re.finditer(r"\b(?:writeFile(?:Sync)?|appendFile(?:Sync)?)\s*\(\s*(?:['\"]([^'\"\n]+)['\"]|(\w+))", body):
            value = m[1] or env.get(m[2])
            if value:
                literals.append(value)
        literals.extend(re.findall(r"\bscreenshot\s*\(\s*\{\s*path:\s*['\"]([^'\"\n]+)['\"]", body))
    result = []
    for value in literals:
        if FILE_LITERAL.match(value) and len(value) < 4096:
            p = path_of(value, cwd)
            if p:
                result.append(p)
    return list(dict.fromkeys(result))


def script_arguments(args):
    """Separate positionals from option values without assuming flag schemas."""
    positional, option_values, outputs = [], [], []
    output_flags = {"-o", "--output", "--out", "--output-file"}
    i, literal = 0, False
    while i < len(args):
        arg = args[i]
        if arg == "--" and not literal:
            literal = True
        elif not literal and (arg.startswith("--") or arg == "-o"):
            key, eq, value = arg.partition("=")
            if not eq and i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                value = args[i]
            if value:
                (outputs if key in output_flags else option_values).append(value)
        elif literal or not arg.startswith("-"):
            positional.append(arg)
        i += 1
    return positional, option_values, outputs


def analyze(command, cwd):
    clean, bodies = heredocs(command)
    body_markers = {doc["marker"]: doc for doc in bodies}
    reads, writes, executed, unresolved = [], [], [], []
    current = cwd
    variables = {"PWD": cwd or os.getcwd(), "HOME": str(Path.home())}
    pipeline_reads = []
    output_separators = []
    for tokens, separator in segments(clean):
        command_bodies = [body_markers[t] for t in tokens if t in body_markers]
        tokens = [t for t in tokens if t not in body_markers]
        if not tokens:
            continue
        while tokens and re.match(r"^[A-Za-z_]\w*=", tokens[0]):
            key, value = tokens[0].split("=", 1)
            # `W="$(pwd)"` / `W=$PWD` 是记下当前目录的常见写法。
            if value in ("$(pwd)", "`pwd`", "$PWD", "${PWD}"):
                value = current or variables["PWD"]
            value = expand_known(value, variables)
            if not any(x in value for x in ("$", "`")):
                variables[key] = value
            tokens = tokens[1:]
        if not tokens:
            continue
        tokens = [expand_known(token, variables) for token in tokens]
        name = os.path.basename(tokens[0])
        args = tokens[1:]
        if name == 'echo' and args and not re.fullmatch(r'-[neE]+', args[0]) and not any(a in ('>', '>>', '<') for a in args) and separator not in ('|', '|&'):
            output_separators.append(' '.join(args))
        if current and re.fullmatch(r"python(?:\d+(?:\.\d+)*)?|node|ruby|perl", name):
            for doc in command_bodies:
                for p in inline_paths(doc["body"], current):
                    writes.append({"path": p, "method": "命令改了它", "evidence": "内联脚本文件名与写入迹象", "inputs": []})
        if name == "cd":
            dest = next((a for a in args if not a.startswith("-")), "~")
            current = path_of(dest, current)
            if current:
                variables["PWD"] = current
            if current is None:
                unresolved.append("cd 包含不能静态解析的路径")
            continue
        # Redirection is independent of the command, including heredoc headers.
        redir_positions = set()
        for i, a in enumerate(args):
            if a in (">", ">>") and i + 1 < len(args):
                p = path_of(args[i + 1], current) if current else None
                redir_positions.update((i, i + 1))
                if p and p not in ("/dev/null", "/dev/stdout", "/dev/stderr"):
                    row = {"path": p, "method": "命令追加" if a == ">>" else "命令写出", "evidence": "重定向", "inputs": []}
                    if name == 'cat' and len(command_bodies) == 1:
                        body = command_bodies[0]
                        other_args = [v for j, v in enumerate(args) if j not in (i, i + 1) and v != '-']
                        if not other_args and (body['literal'] or not any(c in body['body'] for c in ('$','`','\\'))):
                            row.update(literal_content=body['body'], content_kind='append' if a == '>>' else 'full')
                    writes.append(row)
        plain_args = [a for i, a in enumerate(args) if i not in redir_positions]
        if name == "tee":
            for a in plain_args:
                if not a.startswith("-"):
                    p = path_of(a, current) if current else None
                    if p:
                        writes.append({"path": p, "method": "命令追加" if "-a" in args or "--append" in args else "命令写出", "evidence": "tee", "inputs": []})
        if name in READERS:
            files, coverage, options = reader_args(name, plain_args)
            editing = name == "sed" and any(k.startswith("-i") for k in options)
            local_reads = []
            for token in files:
                p = path_of(token, current) if current else None
                if not p:
                    unresolved.append(token)
                    continue
                matches = sorted(glob.glob(p)) if glob.has_magic(p) else [p]
                for match in matches:
                    if Path(match).is_dir():
                        continue
                    if editing:
                        writes.append({"path": match, "method": "命令改了它", "evidence": "sed -i", "inputs": []})
                    else:
                        row = {"path": match, "method": "Bash " + name, "coverage": coverage.copy(),
                               "output_groups": [len(output_separators)]}
                        reads.append(row)
                        local_reads.append(row)
            if not files and coverage["kind"] == "partial":
                for row in pipeline_reads:
                    row["coverage"] = {"kind": "partial", "label": row["coverage"]["label"] + " → " + coverage["label"], "selectors": row["coverage"]["selectors"] + coverage["selectors"]}
            pipeline_reads.extend(local_reads)
        if name in INTERPRETERS or re.search(r"\.(?:py|js|mjs|sh|rb)$", tokens[0]):
            inline = None
            for flag in ("-c", "-e", "--eval"):
                if flag in plain_args and plain_args.index(flag) + 1 < len(plain_args):
                    inline = plain_args[plain_args.index(flag) + 1]
                    break
            if inline is not None:
                for p in inline_paths(inline, current):
                    writes.append({"path": p, "method": "命令改了它", "evidence": "内联脚本文件名与写入迹象", "inputs": []})
            else:
                script_args = list(plain_args) if name in INTERPRETERS else [tokens[0]] + plain_args
                # A '-' script consumes stdin; its heredoc was handled above.
                script_index = next((i for i, a in enumerate(script_args) if not a.startswith("-") or a == "-"), None)
                if script_index is not None:
                    script = script_args[script_index]
                    if script != "-":
                        p = path_of(script, current) if current else None
                        if p:
                            executed.append(p)
                        positional, option_values, output_values = script_arguments(script_args[script_index + 1:])
                        candidates, option_inputs = [], []
                        for a in positional:
                            q = path_of(a, current) if current else None
                            if q and (Path(q).exists() or FILE_LITERAL.match(a)):
                                candidates.append(q)
                        for a in option_values:
                            q = path_of(a, current) if current else None
                            if q and Path(q).exists():
                                option_inputs.append(q)
                        explicit_path = path_of(output_values[-1], current) if output_values and current else None
                        if candidates or explicit_path:
                            files = [x for x in candidates if not Path(x).is_dir()]
                            # A trailing optional image may follow the output.
                            # Prefer the last peer of the primary input's format;
                            # otherwise use the last file argument. This is an
                            # explicitly labelled heuristic, not execution proof.
                            peers = [x for x in files if Path(x).suffix == Path(files[0]).suffix] if files else []
                            output = explicit_path or (peers[-1] if len(peers) > 1 else files[-1] if files else None)
                            if output:
                                explicit_output = explicit_path is not None
                                # Existing arguments outside the primary input's
                                # directory can all be reference inputs (e.g. a
                                # validation command). Keep them as candidates,
                                # but do not invent a producer edge from them.
                                likely_output = explicit_output or not Path(output).exists() or (files[0] != output and Path(files[0]).suffix == Path(output).suffix and Path(files[0]).parent == Path(output).parent)
                                writes.append({"path": output, "method": "命令生成", "evidence": "输出选项" if explicit_output else "命令生成，按命令文字判断", "inputs": list(dict.fromkeys(x for x in candidates + option_inputs if x != output and Path(x).exists())), "script": p, "confidence": "explicit" if explicit_output else "inferred" if likely_output else "ambiguous_argument"})
        if separator not in ("|", "|&"):
            pipeline_reads = []
    merged = {}
    for r in reads:
        if r["path"] not in merged:
            merged[r["path"]] = r
        else:
            old = merged[r["path"]]
            old['output_groups'] = list(dict.fromkeys(old['output_groups'] + r['output_groups']))
            old["method"] = " / ".join(dict.fromkeys((old["method"], r["method"])))
            old["coverage"] = {"kind": "full" if "full" in (old["coverage"]["kind"], r["coverage"]["kind"]) else "partial", "label": old["coverage"]["label"] + "；" + r["coverage"]["label"], "selectors": old["coverage"]["selectors"] + r["coverage"]["selectors"]}
    unique_writes = {}
    for w in writes:
        if w['path'] in unique_writes:
            # Multiple writes to one path in a single shell call do not prove
            # a final full version without interpreting the intervening code.
            unique_writes[w['path']].pop('literal_content', None)
            unique_writes[w['path']].pop('content_kind', None)
        else:
            unique_writes[w['path']] = w
    return {"reads": list(merged.values()), "writes": list(unique_writes.values()), "executed": list(dict.fromkeys(executed)), "unresolved": unresolved,
            "output_separators": output_separators}


def split_output(analysis, text, file_paths):
    """Split only on complete echo lines, in command order.

    Never guess using headings or current file contents. Multiple files in a
    bucket still share that bucket; missing/extra markers fail closed.
    """
    markers = analysis.get('output_separators', [])
    lines = text.splitlines(keepends=True)
    positions = []
    valid = bool(markers)
    hits_by_marker = {marker: [i for i, line in enumerate(lines) if line.rstrip('\r\n') == marker] for marker in set(markers)}
    if any(len(hits) != markers.count(marker) for marker, hits in hits_by_marker.items()):
        valid = False
    for marker in markers:
        hits = hits_by_marker[marker]
        if not hits:
            valid = False
            break
        positions.append(hits.pop(0))
    if positions != sorted(positions):
        valid = False
    rows = {r['path']: r for r in analysis.get('reads', [])}
    if not valid:
        return {p: {'text': text, 'shared_with': [q for q in file_paths if q != p], 'split': False,
                    'ranges': [[0, len(text)]]} for p in file_paths}
    buckets = [''.join(lines[a + 1:b]) for a, b in zip([-1] + positions, positions + [len(lines)])]
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    ranges = [[offsets[a + 1], offsets[b]] for a, b in zip([-1] + positions, positions + [len(lines)])]
    result = {}
    for p in file_paths:
        groups = rows.get(p, {}).get('output_groups', [])
        if not groups or any(g >= len(buckets) for g in groups):
            result[p] = {'text': text, 'shared_with': [q for q in file_paths if q != p], 'split': False,
                         'ranges': [[0, len(text)]]}
            continue
        peers = [q for q in file_paths if q != p and set(groups).intersection(rows.get(q, {}).get('output_groups', []))]
        result[p] = {'text': ''.join(buckets[g] for g in groups), 'shared_with': peers, 'split': True,
                     'ranges': [ranges[g] for g in groups]}
    return result
