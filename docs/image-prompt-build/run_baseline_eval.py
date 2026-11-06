"""基线对照：同一批需求，有 skill（先读 SKILL.md）和没有 skill 各跑一遍，存最终回答。

- 两组同时发出，环境一致；with 组靠路径读 SKILL.md。跑对照前不能正式安装，否则 without 组也会找到它
- 只放只读工具和联网搜索，不放 Bash / Write，避免真去出图
用法：python3 run_baseline_eval.py [--pilot]
"""
import asyncio
import glob
import json
import os
import sys
import time
from pathlib import Path

IMG = os.environ.get('IMAGE_PROMPT_EVAL_IMG', '')


def expand(text):
    """题目里的 {IMG} 换成本机横评图目录（环境变量 IMAGE_PROMPT_EVAL_IMG），仓库里不存本机路径。"""
    if '{IMG}' in text and not IMG:
        raise SystemExit('题目含 {IMG}，先设环境变量 IMAGE_PROMPT_EVAL_IMG 指向参考图目录')
    return text.replace('{IMG}', IMG)

BASE = Path(__file__).resolve().parent
SKILL = BASE.parents[1] / 'skills/image-prompt'
CLI = sorted(glob.glob(os.path.expanduser(
    '~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64/resources/native-binary/claude')))[-1]
MODEL = 'claude-opus-5-5'
TIMEOUT = 900
SCRATCH = Path(os.environ.get('EVAL_SCRATCH', '/tmp')) / 'image-prompt-baseline'


def build_prompt(q, arm):
    if arm == 'without':
        return expand(q['query'])
    return (f'先读 {SKILL}/SKILL.md，按它处理下面这个需求（它提到的 references/ 在同一目录下）。\n\n'
            f'需求：{expand(q["query"])}')


async def run_one(q, arm, sem, outdir):
    key = f"{q['id']}-{arm}"
    done = outdir / f'{key}.json'
    if done.exists():
        return json.loads(done.read_text())
    async with sem:
        work = SCRATCH / key
        work.mkdir(parents=True, exist_ok=True)
        args = [CLI, '-p', build_prompt(q, arm), '--model', MODEL, '--output-format', 'stream-json', '--verbose',
                '--allowedTools', 'Read', 'Glob', 'Grep', 'Skill', 'WebSearch', 'WebFetch',
                '--disallowedTools', 'Bash', 'Write', 'Edit', 'NotebookEdit', 'Agent', 'Workflow',
                'AskUserQuestion']
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(*args, cwd=work, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL, limit=2 ** 26)
        raw, result, tools, model_seen = [], None, [], None
        try:
            async def read():
                nonlocal result, model_seen
                async for line in proc.stdout:
                    raw.append(line)
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get('type') == 'assistant':
                        msg = ev.get('message', {})
                        model_seen = msg.get('model', model_seen)
                        for c in msg.get('content', []):
                            if c.get('type') == 'tool_use':
                                tools.append({'name': c['name'], 'input': c.get('input', {})})
                    if ev.get('type') == 'result':
                        result = ev
            await asyncio.wait_for(read(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            pass
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 10)
                except asyncio.TimeoutError:
                    proc.kill()
        (outdir / f'{key}.stream.jsonl').write_bytes(b''.join(raw))
        text = (result or {}).get('result') or ''
        (outdir / f'{key}.md').write_text(text)
        res = {'id': q['id'], 'arm': arm, 'model': model_seen, 'ok': bool(result) and not result.get('is_error'),
               'cost_usd': (result or {}).get('total_cost_usd'), 'duration_ms': (result or {}).get('duration_ms')
               or round((time.monotonic() - start) * 1000), 'num_turns': (result or {}).get('num_turns'),
               'usage': (result or {}).get('usage'),
               'tools': [t['name'] + (':' + str(t['input'].get('skill') or t['input'].get('file_path', ''))
                                      if t['name'] in ('Skill', 'Read') else '') for t in tools]}
        done.write_text(json.dumps(res, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: res[k] for k in ['id', 'arm', 'ok', 'cost_usd', 'duration_ms', 'model']},
                         ensure_ascii=False), flush=True)
        return res


async def main():
    data = json.loads((BASE / 'baseline-queries.json').read_text())
    queries = data['queries']
    tag = 'pilot' if '--pilot' in sys.argv else 'full'
    if tag == 'pilot':
        queries = [q for q in queries if q['id'] == 'b7']
    if '--v2' in sys.argv:
        queries = [q for q in data['queries'] if q['id'] in os.environ.get('V2_ONLY', 'b1,b5,b10').split(',')]
        tag = 'v2'
    else:
        assert data['user_confirmed'], '先请用户确认对照题'
    link = Path.home() / '.claude/skills/image-prompt'
    assert tag == 'v2' or not (link.is_symlink() or link.exists()), \
        '已正式安装，without 组会找到 skill；先 ./install.sh --uninstall --only image-prompt，跑完再装回'
    outdir = BASE / 'runs' / f'baseline-{tag}'
    outdir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(4)
    arms = ('with',) if tag == 'v2' else ('with', 'without')
    results = await asyncio.gather(*(run_one(q, arm, sem, outdir) for q in queries for arm in arms))
    (BASE / 'runs' / f'baseline-results-{tag}.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
