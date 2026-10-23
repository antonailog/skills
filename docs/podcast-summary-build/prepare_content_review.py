"""Objective local checks and deidentified artifacts for independent content review."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
KEY = {'narrative': {'A': 'with', 'B': 'without'},
       'discussion': {'A': 'without', 'B': 'with'}}


def sections(md):
    matches = list(re.finditer(r'^## (.+)$', md, re.M))
    return {m.group(1): md[m.start():matches[i+1].start() if i+1 < len(matches) else len(md)].strip()
            for i, m in enumerate(matches)}


def checks(case, folder):
    md = (folder / 'note.md').read_text()
    lines = md.splitlines()
    spacing = [i+1 for i, line in enumerate(lines) if re.match(r'^#{1,6} ', line) and i > 0
               and lines[i-1].strip() and not lines[i-1].startswith('#')]
    image = 'choices' if case == 'narrative' else 'subsidy'
    obj = {
        'headings_spaced': not spacing,
        'shownotes_image': bool(re.search(r'!\[[^\]]*\]\([^\n)]*'+image+r'\.svg\)', md)),
        'overview_embedded': bool(re.search(r'!\[[^\]]*\]\([^\n)]*overview\.svg\)', md)),
        'core_sections': all(s in md for s in ['总结', '关键要点', 'Shownotes']),
        'metadata': all(s in md for s in (['选择的温度','林舟','许禾','2025-09-12','42']
                                          if case == 'narrative' else ['城市生活实验室','租房补助该按月发，还是直接抵租金'])),
    }
    if case == 'discussion':
        old = (BASE / 'fixtures/discussion/current-note.md').read_text()
        previous, new = sections(old), sections(md)
        protection = {
            'title': re.findall(r'^# .+$', old, re.M) == re.findall(r'^# .+$', md, re.M),
            'order': list(previous) == list(new),
            'personal': previous['我的思考和记录'] == new.get('我的思考和记录'),
            'shownotes': previous['Shownotes'] == new.get('Shownotes'),
            'other': all(v == new.get(k) for k,v in previous.items()
                         if k not in ['关键内容','我的思考和记录','Shownotes']),
        }
    else:
        personal = next((v for k,v in sections(md).items() if '个人思考' in k or '我的思考' in k), '')
        # This only establishes an empty/placeholder slot. R1 covers any invented first-person claims elsewhere.
        body = '\n'.join(l for l in personal.splitlines() if not l.startswith('#')).strip()
        slot_lines = [line.strip() for line in re.sub(r'<!--.*?-->', '', body, flags=re.S).splitlines() if line.strip()]
        empty_slots = all(re.search(r'_{3,}|待填写|待补充|待记录', line) for line in slot_lines)
        protection = {'personal_slot_empty': bool(personal) and empty_slots}
    svg = ET.parse(folder/'overview.svg').getroot()
    valid_svg = svg.tag.split('}')[-1] == 'svg'
    texts = [e for e in svg.iter() if e.tag.split('}')[-1] == 'text']
    render = subprocess.run(['rsvg-convert', str(folder/'overview.svg'), '-o', str(folder/'overview.png')],
                            capture_output=True, text=True)
    r7 = sum(protection.values()) if case == 'discussion' else (5 if all(protection.values()) else 0)
    return {'case':case, 'R6':sum(obj.values()), 'R7':r7,
            'format_checks':obj,'protection_checks':protection,
            'spacing_error_lines':spacing, 'svg_xml_valid':valid_svg,
            'svg_text_elements':len(texts), 'svg_rendered':render.returncode == 0,
            'render_error':render.stderr,
            'emphasis_counts':{'bold':len(re.findall(r'\*\*[^*]+\*\*',md)),
                               'highlight':len(re.findall(r'<mark\b|==[^=]+==',md)),
                               'underline':len(re.findall(r'<u>',md))}}


def main():
    objective = []
    for case, labels in KEY.items():
        for label, condition in labels.items():
            src = BASE / 'runs/baseline' / f'{case}-{condition}'
            result = checks(case, src)
            result.update(label=label,condition=condition)
            objective.append(result)
            dst = BASE / 'runs/blind' / case / label
            dst.mkdir(parents=True, exist_ok=True)
            for name in ['note.md','overview.svg','overview.png','content-plan.md','validation.txt']:
                shutil.copyfile(src/name, dst/name)
            shutil.copytree(src/'assets', dst/'assets', dirs_exist_ok=True)
            for source in ['transcript.md','shownotes.md','current-note.md']:
                fixture = BASE/'fixtures'/case/source
                if fixture.exists():
                    shutil.copyfile(fixture, src/source)
                    shutil.copyfile(fixture, dst/source)
            events = [json.loads(l) for l in (src/'events.jsonl').read_text().splitlines() if l.startswith('{')]
            commands = [e['item'] for e in events if e.get('type') == 'item.completed'
                        and e.get('item',{}).get('type') == 'command_execution']
            provenance = {
                'transcript_read_command_succeeded': any('transcript.md' in e.get('command','') and e.get('exit_code') == 0 for e in commands),
                'shownotes_read_command_succeeded': any('shownotes.md' in e.get('command','') and e.get('exit_code') == 0 for e in commands),
                'generation_xml_check_command_succeeded': any(('ET.fromstring' in e.get('command','') or 'ElementTree.fromstring' in e.get('command','')) and e.get('exit_code') == 0 for e in commands),
                'remote_writes': 'not part of the test; no account tools provided',
                'image_render': 'review harness rendered the submitted SVG with rsvg-convert after generation; not evidence of rendering by the author',
            }
            (dst/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
            (dst/'objective.json').write_text(json.dumps({k:v for k,v in result.items() if k!='condition'},ensure_ascii=False,indent=2)+'\n')
    (BASE/'objective-results.json').write_text(json.dumps(objective,ensure_ascii=False,indent=2)+'\n')
    (BASE/'runs/blind-key.json').write_text(json.dumps(KEY,indent=2)+'\n')
    print(json.dumps(objective,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
