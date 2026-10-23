"""Controlled first-preparation-step routing checks; offline fixtures, read-only child."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import tomllib

BASE = Path(__file__).resolve().parent
PACKAGE = BASE.parents[1] / 'skills/podcast-summary'
CLI = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'


def configuration():
    config = tomllib.loads(Path('~/.codex/config.toml').expanduser().read_text())
    return {key: config[key] for key in ['model', 'model_reasoning_effort', 'service_tier'] if key in config}


async def run_one(query, run, semaphore, conf):
    key = f'{query["id"]}-{run}'
    output = BASE / 'runs/trigger' / key
    output.mkdir(parents=True, exist_ok=True)
    done = output / 'metrics.json'
    if done.exists():
        return json.loads(done.read_text())
    async with semaphore:
        with tempfile.TemporaryDirectory(prefix='podcast-routing-') as td:
            work = Path(td)
            skills = work / '.agents/skills'
            skills.mkdir(parents=True)
            (skills / 'podcast-summary').symlink_to(PACKAGE, target_is_directory=True)
            (work / '资料').mkdir()
            for name in ['返乡访谈.txt', 'agent.txt', 'episode.txt']:
                (work / '资料' / name).write_text('本地离线样本。来宾讨论选择条件、不同观点、案例和未确定的事项。\n')
            (work / 'AGENTS.md').write_text('这是离线的首个准备步骤测试。保持正常的工具与技能选择，可以直接读取材料或读取适用技能。只完成第一个准备步骤并简述下一步，然后结束；不要生成最终笔记，不要写文件或调用外部服务。资料均为测试夹具，不使用任何真实账号内容。\n')
            args = [CLI, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                    '--sandbox', 'read-only', '--json', '-C', str(work),
                    '-o', str(output / 'final.txt')]
            for k, v in conf.items():
                args += ['-c', f'{k}={json.dumps(v)}']
            args += ['-']
            prompt = query['query']
            (output / 'prompt.txt').write_text(prompt)
            start = time.monotonic()
            with (output / 'events.jsonl').open('wb') as stdout, (output / 'stderr.txt').open('wb') as stderr:
                proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
                                                           stdout=stdout, stderr=stderr)
                try:
                    await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=600)
                except asyncio.TimeoutError:
                    proc.terminate()
                    await proc.wait()
            duration = round((time.monotonic() - start) * 1000)
            events = []
            for line in (output / 'events.jsonl').read_text(errors='replace').splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            actions = [e['item'] for e in events if e.get('type') == 'item.completed'
                       and e.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call')]
            reads = [x for x in actions if 'podcast-summary' in str(x.get('command', ''))
                     and 'SKILL.md' in str(x.get('command', '')) and x.get('exit_code') == 0]
            completed = [e for e in events if e.get('type') == 'turn.completed']
            usage = completed[-1].get('usage') if completed else None
            result = {'id': query['id'], 'run': run, 'split': query['split'],
                      'expected': query['should_trigger'], 'observed_skill_read': bool(reads),
                      'returncode': proc.returncode, 'turn_completed': bool(completed),
                      'duration_ms': duration, 'usage': usage,
                      'commands': [x.get('command') for x in actions], 'settings': conf}
            done.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({k: result[k] for k in ['id', 'run', 'returncode', 'turn_completed',
                                                     'observed_skill_read', 'duration_ms']}, ensure_ascii=False), flush=True)
            return result


async def main():
    data = json.loads((BASE / 'trigger-eval.json').read_text())
    assert data['user_confirmed']
    queries = data['queries']
    if '--pilot' in sys.argv:
        queries = queries[:1]
        repeats = 1
    else:
        repeats = data['runs_per_query']
    semaphore = asyncio.Semaphore(3)
    conf = configuration()
    results = await asyncio.gather(*(run_one(q, r, semaphore, conf)
                                    for r in range(1, repeats + 1) for q in queries))
    name = 'trigger-pilot.json' if '--pilot' in sys.argv else 'trigger-results.json'
    (BASE / name).write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
