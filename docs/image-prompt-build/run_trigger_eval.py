"""触发评测：每条 query 起一个无界面 Claude Code，看前几次工具调用里有没有 Skill(image-prompt)。

- 用 VS Code 扩展自带的新版 claude（终端那个旧版认不了 claude-opus-5-5）
- 没装时临时软链进 ~/.claude/skills、结束删掉；已经装好（指向同一个包）就沿用，不删
- 只放只读工具，不放 Bash / Write / 联网，避免真去出图或改文件
- 看到 Skill 调用或者满 MAX_TOOLS 次工具调用就停，省钱
用法：python3 run_trigger_eval.py [--pilot] [--runs N]
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
PACKAGE = BASE.parents[1] / 'skills/image-prompt'
LINK = Path.home() / '.claude/skills/image-prompt'
CLI = sorted(glob.glob(os.path.expanduser(
    '~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64/resources/native-binary/claude')))[-1]
MODEL = 'claude-opus-5-5'
MAX_TOOLS = 3
TIMEOUT = 180
SCRATCH = Path(os.environ.get('EVAL_SCRATCH', '/tmp')) / 'image-prompt-trigger'


async def run_one(q, run, sem, outdir):
    key = f"{q['id']}-{run}"
    done = outdir / f'{key}.json'
    if done.exists():
        return json.loads(done.read_text())
    async with sem:
        work = SCRATCH / key
        work.mkdir(parents=True, exist_ok=True)
        args = [CLI, '-p', expand(q['query']), '--model', MODEL, '--output-format', 'stream-json', '--verbose',
                '--allowedTools', 'Read', 'Glob', 'Grep', 'Skill',
                '--disallowedTools', 'Bash', 'Write', 'Edit', 'WebSearch', 'WebFetch', 'Agent', 'Workflow']
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(*args, cwd=work, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL, limit=2 ** 26)
        tools, model_seen, cost, raw = [], None, None, []
        try:
            async def read():
                nonlocal model_seen, cost
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
                                if c['name'] == 'Skill' or len(tools) >= MAX_TOOLS:
                                    return
                    if ev.get('type') == 'result':
                        cost = ev.get('total_cost_usd')
                        return
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
        skills = [t['input'].get('skill') for t in tools if t['name'] == 'Skill']
        res = {'id': q['id'], 'run': run, 'split': q['split'], 'expected': q['should_trigger'],
               'triggered': 'image-prompt' in skills, 'skills_called': skills,
               'tools': [t['name'] for t in tools], 'model': model_seen, 'cost_usd': cost,
               'duration_ms': round((time.monotonic() - start) * 1000)}
        (outdir / f'{key}.stream.jsonl').write_bytes(b''.join(raw))
        done.write_text(json.dumps(res, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: res[k] for k in ['id', 'run', 'expected', 'triggered', 'skills_called', 'tools', 'model']},
                         ensure_ascii=False), flush=True)
        return res


async def main():
    data = json.loads((BASE / 'trigger-eval.json').read_text())
    queries = data['queries']
    runs = data['runs_per_query']
    if '--runs' in sys.argv:
        runs = int(sys.argv[sys.argv.index('--runs') + 1])
    tag = 'pilot' if '--pilot' in sys.argv else 'full'
    if tag == 'pilot':
        queries, runs = [q for q in queries if q['id'] in ('t4', 'n1')], 1
    else:
        assert data['user_confirmed'], '先请用户确认 query 集'
    outdir = BASE / 'runs' / f'trigger-{tag}'
    outdir.mkdir(parents=True, exist_ok=True)
    present = LINK.is_symlink() or LINK.exists()
    assert not present or LINK.resolve() == PACKAGE.resolve(), f'{LINK} 已存在且指向别处，先人工确认'
    created = False
    if not present:
        LINK.symlink_to(PACKAGE, target_is_directory=True)
        created = True
    try:
        sem = asyncio.Semaphore(4)
        results = await asyncio.gather(*(run_one(q, r, sem, outdir) for r in range(1, runs + 1) for q in queries))
    finally:
        if created and LINK.is_symlink():
            LINK.unlink()
        print('symlink:', 'removed (created by this run)' if created else 'kept (pre-existing install)')
    (BASE / f'trigger-results-{tag}.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
