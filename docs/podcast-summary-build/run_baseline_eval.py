"""Paired, offline content evaluation. Actual model outputs, no remote document writes."""
import asyncio
import json
from pathlib import Path
import shutil
import tempfile
import time

from run_trigger_eval import CLI, BASE, PACKAGE, configuration

SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {key: {'type': 'string'} for key in
                   ['content_plan', 'note_markdown', 'overview_svg', 'validation_status']},
    'required': ['content_plan', 'note_markdown', 'overview_svg', 'validation_status'],
}
QUERIES = {
    'narrative': '这期三次换工作的播客听完了。请根据完整原文和 Shownotes 整理一份本地笔记，包含播客信息、总结、关键要点、一张说明整期内容的 SVG、我的个人思考空位。',
    'discussion': '这期租房补助的播客笔记太浅了。按 current-note.md 我现在维护的标题和栏目位置，只重写关键内容里的总览、总结、关键要点，图要有详细信息。本次只交付完整本地笔记与 SVG，不写飞书。',
}


async def run_one(case, condition, conf, semaphore):
    out = BASE / 'runs/baseline' / f'{case}-{condition}'
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'metrics.json').exists():
        return json.loads((out / 'metrics.json').read_text())
    async with semaphore:
        with tempfile.TemporaryDirectory(prefix='podcast-content-') as td:
            work = Path(td)
            shutil.copytree(BASE / 'fixtures' / case, work, dirs_exist_ok=True)
            if condition == 'with':
                (work / '.agents/skills').mkdir(parents=True)
                (work / '.agents/skills/podcast-summary').symlink_to(PACKAGE, target_is_directory=True)
            (work / 'AGENTS.md').write_text(
                '这是离线合成材料评测。只读取当前工作目录提供的材料和其中可用的技能引用；不读取其他工作目录、私人资料、账号或主目录文档，不使用其他技能。不要访问网络或写外部服务。'
                '最终按 JSON schema 返回实际内容，overview_svg 为完整合法 SVG 源码，note_markdown 中用 ./overview.svg 引用它。'
                '本次交付限定为本地文字和 SVG，不要求原生画板、XMind 或远端写入；不用为本测试创建项目管理文件。'
                '没有完成的浏览器、飞书或其他检查如实说明；可以在只读工具中检查内容。\n')
            schema = out / 'schema.json'
            schema.write_text(json.dumps(SCHEMA))
            args = [CLI, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                    '--sandbox', 'read-only', '--json', '-C', str(work), '--output-schema', str(schema),
                    '-o', str(out / 'response.json')]
            for k, v in conf.items():
                args += ['-c', f'{k}={json.dumps(v)}']
            args += ['-']
            prompt = QUERIES[case]
            (out / 'prompt.txt').write_text(prompt)
            start = time.monotonic()
            with (out / 'events.jsonl').open('wb') as stdout, (out / 'stderr.txt').open('wb') as stderr:
                proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=stdout, stderr=stderr)
                try:
                    await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=900)
                except asyncio.TimeoutError:
                    proc.terminate()
                    await proc.wait()
            elapsed = round((time.monotonic() - start) * 1000)
            events = []
            for line in (out / 'events.jsonl').read_text(errors='replace').splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            completed = [e for e in events if e.get('type') == 'turn.completed']
            commands = [e['item'].get('command', '') for e in events
                        if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'command_execution']
            result = {'case': case, 'condition': condition, 'returncode': proc.returncode,
                      'turn_completed': bool(completed), 'duration_ms': elapsed,
                      'usage': completed[-1].get('usage') if completed else None,
                      'skill_read': any('podcast-summary' in c and 'SKILL.md' in c for c in commands),
                      'commands': commands, 'settings': conf}
            try:
                data = json.loads((out / 'response.json').read_text())
                for key, name in [('note_markdown', 'note.md'), ('overview_svg', 'overview.svg'),
                                  ('content_plan', 'content-plan.md'), ('validation_status', 'validation.txt')]:
                    (out / name).write_text(data[key])
                shutil.copytree(work / 'assets', out / 'assets', dirs_exist_ok=True)
                result['valid_json_output'] = True
            except (OSError, KeyError, ValueError):
                result['valid_json_output'] = False
            (out / 'metrics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({k:result[k] for k in ['case','condition','returncode','turn_completed','duration_ms','skill_read','valid_json_output']}, ensure_ascii=False), flush=True)
            return result


async def main():
    conf = configuration()
    # Both treatments are scheduled together with identical model settings.
    semaphore = asyncio.Semaphore(4)
    results = await asyncio.gather(*(run_one(case, condition, conf, semaphore)
                                    for case in QUERIES for condition in ['with', 'without']))
    (BASE / 'baseline-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
