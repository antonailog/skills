#!/usr/bin/env python3
"""改稿时查作者以前不止一次改掉的说法。

用法：python3 check_repeats.py <稿子.md>

列出每一处命中：第几行、命中的字、所在的句子、作者当时改成了什么方向。
命中只是嫌疑，回到上下文看，放在那里确实说得通的就留着。

词表只收作者在两篇以上、或者同一篇两处以上改掉的说法，来源是项目里的反馈账本；
和题目有关的名词不收。加一条以前先确认作者真的改过两次以上。
"""
import re
import sys

# (正则, 作者改成的方向)
PATTERNS = [
    (r"(?<![推反])翻(?!译|倍|身|新|番|转|开|看|阅|墙|车|脸|盖)", "单字压缩，作者改成「搜集」「浏览」「看一遍」这类完整的说法"),
    (r"攒", "单字压缩，作者改成「收集」这类完整的说法"),
    (r"(?<![分扩解松拆闲涣发])散(?!步|文|会|装|开|发|落|热|伙|了)", "单字压缩，作者说「散」太简单，说清是分布在哪几个地方"),
    (r"挡", "单字压缩，作者改成「拦下」这类完整的说法"),
    (r"(?<![体总独仲制])裁(?!剪|判|员|定|决|缝)", "单字压缩，作者改成「裁剪」"),
    (r"(?<![暴透显披揭流])露(?!出|面|营|天|水|台|珠|骨)", "单字压缩，作者改成「显示」"),
    (r"(?<![审考结细])核(?!对|实|查|心|算|桃|酸|销|准|电|武)", "单字压缩，作者改成「核对」"),
    (r"筛(?!选|子|查)", "单字压缩，作者改成「筛选」"),
    (r"留个", "作者说过「留给谁呀」，说读者真正在做的那件事，比如「输入邮箱订阅」「预约」"),
    (r"真要", "无用的强调，作者删过，直接说事"),
    (r"更麻烦的是|真正的问题是", "说事之前先强调，作者改成「而且」「但」这类平常的接法"),
]

SENT_END = re.compile(r"[。！？!?]")


def sentence_around(line, start, end):
    left = max((m.end() for m in SENT_END.finditer(line, 0, start)), default=0)
    m = SENT_END.search(line, end)
    right = m.end() if m else len(line)
    return line[left:right].strip()


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    text = open(sys.argv[1], encoding="utf-8").read().splitlines()
    hits = 0
    for no, line in enumerate(text, 1):
        if re.fullmatch(r"\s*\[(图|视频)\d+\]\s*|\s*\[公众号二维码\]\s*", line):
            continue
        for pat, hint in PATTERNS:
            for m in re.finditer(pat, line):
                hits += 1
                print(f"第 {no} 行「{m.group(0)}」：{sentence_around(line, m.start(), m.end())}")
                print(f"    {hint}")
    print(f"共 {hits} 处。" if hits else "没有命中。")


if __name__ == "__main__":
    main()
