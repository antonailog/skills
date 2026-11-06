"""对照评分：客观检查（脚本）+ 盲评（无界面 Claude，每题 3 次，A/B 顺序随机），汇总成 score_rubric.py 的输入。

用法：python3 judge_and_score.py            # 跑客观检查和盲评（已有结果会跳过）
      python3 judge_and_score.py --objective-only
"""
import asyncio
import glob
import json
import os
import random
import re
import sys
from pathlib import Path

IMG = os.environ.get('IMAGE_PROMPT_EVAL_IMG', '')


def expand(text):
    """题目里的 {IMG} 换成本机横评图目录（环境变量 IMAGE_PROMPT_EVAL_IMG），仓库里不存本机路径。"""
    if '{IMG}' in text and not IMG:
        raise SystemExit('题目含 {IMG}，先设环境变量 IMAGE_PROMPT_EVAL_IMG 指向参考图目录')
    return text.replace('{IMG}', IMG)

BASE = Path(__file__).resolve().parent
RUNS = BASE / os.environ.get('JUDGE_RUNS', 'runs/baseline-full')
JUDGE = BASE / os.environ.get('JUDGE_OUT', 'runs/judge')
ONLY = [x for x in os.environ.get('JUDGE_ONLY', '').split(',') if x]
SUFFIX = os.environ.get('JUDGE_SUFFIX', '')
CLI = sorted(glob.glob(os.path.expanduser(
    '~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64/resources/native-binary/claude')))[-1]
MODEL = 'claude-opus-5-5'
SAMPLES = 3

APPLY = {
    'b1': ['K1', 'K2', 'K3', 'K7', 'K8', 'K9', 'K10', 'K12', 'U'],
    'b2': ['K2', 'K3', 'K7', 'K8', 'K9', 'K10', 'U'],
    'b3': ['K2', 'K3', 'K4', 'K7', 'K8', 'K9', 'K10', 'K12', 'U'],
    'b4': ['K2', 'K3', 'K7', 'K10', 'K11', 'U'],
    'b5': ['K2', 'K5', 'K10', 'U'],
    'b6': ['K1', 'K2', 'K3', 'K7', 'K9', 'K10', 'K13', 'U'],
    'b7': ['K2', 'K3', 'K4', 'K7', 'K8', 'K9', 'K10', 'U'],
    'b8': ['K2', 'K3', 'K4', 'K7', 'K8', 'K9', 'K10', 'U'],
    'b9': ['K2', 'K3', 'K7', 'K10', 'K11', 'U'],
    'b10': ['K2', 'K3', 'K7', 'K8', 'K9', 'K10', 'U'],
}
REQUIRED_TEXT = {
    'b3': ['在线等，挺急的', '一个总在线，一个总在摸鱼', '11月11日'],
    'b7': ['未来已来'],
    'b8': ['卵', '幼虫', '蛹', '成虫'],
}
ID_OK = {'gpt-image-2.6-flare', 'gpt-image-2.6-sunburst', 'gpt-image-2.5-flare', 'gpt-image-2.5-sunburst',
         'gpt-image-2.5-flare-2026-09-08', 'gpt-image-2.5-sunburst-2026-09-08', 'gemini-3-pro-image',
         'gemini-nano-banana-2.1', 'gemini-3.1-flash-image', 'doubao-seedream-5-0-pro-260628',
         'doubao-seedream-5-0-flash-260915'}
BANNED = re.compile(r'masterpiece|best quality|\b8k\b|超高清|大师作品|杰作|\bCFG\b|\bsteps\b|sampler|euler|negative prompt',
                    re.I)

RUBRIC = (BASE / '04-考点表.md').read_text().split('客观检查')[0]
FACTS = """事实表（2026-11-06 核自官方文档；与此不符的参数说法算错，事实表没提到的参数当作不存在）：
- GPT Image 2.6：模型 ID gpt-image-2.6-flare（偏速度）/ gpt-image-2.6-sunburst（偏细节、版式、编辑精度）；只能走 Image API（/v1/images/generations、/v1/images/edits），不支持 Responses API。quality：auto/low/medium/high/xhigh/max。complexity：low/medium/high，不传默认 high；只改一处细节的编辑从 low 开始；prompt 已写死版式文字时调高差别不大。size：两边 16 的倍数、比例 1:3 到 3:1，单边上限官方未写。output_format 可为 svg（仅 generations，n=1）或 gif（frame_count 2–16 默认 9，frame_duration_ms 20–2000 默认 200）。markup 编辑：另传同尺寸透明 PNG 标注。没有 seed、negative_prompt、CFG、steps、style。
- GPT Image 2.5：gpt-image-2.5-flare / -sunburst；quality 同上六档；没有 complexity、GIF、SVG；size 单边 ≤3840、16 的倍数、比例 ≤3:1；支持 markup。
- codex 内置生图：没有可调参数，不是 2.6。
- Nano Banana Pro：gemini-3-pro-image（-preview 已关停）；image_size 1K/2K/4K（大写 K，默认 1K）；aspect_ratio 1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9；不设比例则跟随输入图或出 1:1；参考图最多 14（物体 6、人物 5、风格 3）；参数写在 Interactions API 的 response_format（aspect_ratio、image_size）或旧接口 imageConfig（aspectRatio、imageSize）；没有 negative prompt、guidance、CFG。
- Nano Banana 2.1：gemini-nano-banana-2.1（2026-10-06 GA，Pro 的高效版，官方没说比 Pro 强）；thinking_level minimal/medium/high（默认 medium）；image_size 1K/2K/4K；比例比 Pro 多 1:4 4:1 1:8 8:1；参考图物体 10、人物 4；传 seed/temperature/topP/topK 会报错。
- Seedream 5.0 Pro：doubao-seedream-5-0-pro-260628；size 只有 1K/1.5K/2K（默认 2K）或宽x高（总像素 921,600–4,624,220），没有 4K；官方推荐比例用自然语言写进 prompt；中文 prompt 建议不超过 300 字；画面文字用双引号；参考图最多 10 张；不支持组图（sequential_image_generation）、联网搜索；watermark 默认 true（右下角「AI 生成」）；参数表里没有 seed、guidance_scale。另有 Seedream 5.0 Flash：doubao-seedream-5-0-flash-260915，能力同 Pro；5.0 Lite（doubao-seedream-5-0-260128）真实存在但 2026-11-24 关停，推荐它要扣分但不算编造。
- 价格参考（Google 官方）：Nano Banana Pro 约 0.134 美元/张（1K/2K）、0.24（4K）；2.1 约 0.034（1K）、0.050（2K）、0.113（4K）。
"""


def code_blocks(text):
    return re.findall(r'```[a-zA-Z]*\n(.*?)```', text, re.S)


def objective(qid, text):
    blocks = code_blocks(text)
    joined = '\n'.join(blocks)
    o = {}
    o['O1'] = 0 if BANNED.search(joined) else 2
    ids = set(re.findall(r'(?:gpt-image-[0-9a-z.\-]+|gemini-[0-9a-z.\-]+|doubao-seedream-[0-9a-z\-]+)', text, re.I))
    ids = {i.rstrip('.-').lower() for i in ids}
    if ids:
        o['O2'] = 2 if ids <= ID_OK else 0
        o['O2_bad'] = sorted(ids - ID_OK)
    if qid in REQUIRED_TEXT:
        need = REQUIRED_TEXT[qid]
        hit = sum(1 for s in need if s in joined)
        o['O3'] = 2 if hit == len(need) else (1 if hit else 0)
    if qid == 'b10':
        zh = [b for b in blocks if re.search(r'[一-鿿]', b)]
        longest = max((len(re.sub(r'\s', '', b)) for b in zh), default=0)
        o['O4'] = 2 if 0 < longest <= 300 else 0
        o['O4_len'] = longest
    o['n_blocks'] = len(blocks)
    return o


def judge_prompt(q, a, b, keys):
    return f"""你是生图 prompt 的评审。下面是同一个需求的两份回答 A 和 B，你不知道它们分别是怎么产生的。按考点逐条给 A 和 B 各打 0–2 分。

## 需求
{expand(q['query'])}

## 只评这些考点
{', '.join(keys)}

## 考点说明
{RUBRIC}

## {FACTS}

## 回答 A
{a}

## 回答 B
{b}

## 要求
- 不要调用任何工具，只根据上面的文字判断。图片你看不到，涉及原图内容的考点按回答描述的完整度和合理性判。
- 判「做到」要求真的做到，不是表面合规。
- 只输出一个 JSON 对象，不要别的文字：
{{"A": {{"K2": 2, ...}}, "B": {{"K2": 1, ...}}, "why": "每个考点一句话说明两边差在哪", "rubric_critique": "哪条考点模糊、重复或两边都必然满分，没有就写 null"}}
"""


async def judge_one(q, sample, sem):
    out = JUDGE / f"{q['id']}-{sample}.json"
    if out.exists():
        return json.loads(out.read_text())
    w = (RUNS / f"{q['id']}-with.md").read_text()
    wo = (RUNS / f"{q['id']}-without.md").read_text()
    rnd = random.Random(f"{q['id']}-{sample}")
    with_is_a = rnd.random() < 0.5
    a, b = (w, wo) if with_is_a else (wo, w)
    prompt = judge_prompt(q, a, b, APPLY[q['id']])
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            CLI, '-p', prompt, '--model', MODEL, '--output-format', 'json',
            '--disallowedTools', 'Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'WebSearch', 'WebFetch', 'Agent',
            'Skill', 'Workflow', cwd=str(JUDGE), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            limit=2 ** 26)
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
    env = json.loads(stdout)
    text = env.get('result', '')
    parsed = json.loads(text[text.find('{'):text.rfind('}') + 1])
    res = {'id': q['id'], 'sample': sample, 'with_is_a': with_is_a,
           'with': parsed['A'] if with_is_a else parsed['B'], 'without': parsed['B'] if with_is_a else parsed['A'],
           'why': parsed.get('why'), 'rubric_critique': parsed.get('rubric_critique'),
           'cost_usd': env.get('total_cost_usd'), 'model': list((env.get('modelUsage') or {}).keys())}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: res[k] for k in ['id', 'sample', 'with_is_a', 'with', 'without', 'model']},
                     ensure_ascii=False), flush=True)
    return res


async def main():
    queries = json.loads((BASE / 'baseline-queries.json').read_text())['queries']
    if ONLY:
        queries = [q for q in queries if q['id'] in ONLY]
    obj = {q['id']: {arm: objective(q['id'], (RUNS / f"{q['id']}-{arm}.md").read_text())
                     for arm in ('with', 'without')} for q in queries}
    (BASE / f'objective-results{SUFFIX}.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(obj, ensure_ascii=False))
    if '--objective-only' in sys.argv:
        return
    JUDGE.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(5)
    results = await asyncio.gather(*(judge_one(q, s, sem) for q in queries for s in range(1, SAMPLES + 1)))
    for arm in ('with', 'without'):
        rows = []
        for r in results:
            scores = {k: v for k, v in r[arm].items() if isinstance(v, (int, float))}
            for k, v in obj[r['id']][arm].items():
                if k in ('O1', 'O2', 'O3', 'O4'):
                    scores[k] = v
            rows.append({'query_id': r['id'], 'run': r['sample'], 'scores': scores})
        (BASE / f'scores-{arm}{SUFFIX}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
