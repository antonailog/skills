import { useBilingual } from '@/components/Bilingual'
import { CopyBtn } from '@/components/CopyBtn'

/** 提示词块：```prompt 代码块、宽表卡片里整格是行内代码的格子。浅强调色底，右上角复制（复制当前语言） */
export function Say({ t }: { t: string }) {
  const { has, shown, bar } = useBilingual(t)
  return (
    <div className={has ? 'say bi' : 'say'}>
      {bar}
      <CopyBtn className="say-copy" text={shown} />
      {shown.split('\n').map((l, i) => <p key={i}>{l || ' '}</p>)}
    </div>
  )
}
