import type { CSSProperties } from "react";

import type { TierProgress } from "../../../entities/loyalty/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Money } from "../../../shared/ui/Money";

export function TierProgressCard({ progress, onProgram }: { progress: TierProgress; onProgram: () => void }) {
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const isMaxLevel = progress.next_tier === null;
  const completed = isMaxLevel ? 0 : Math.max(0, Number(progress.next_tier?.minimum_turnover) - Number(progress.current_tier.minimum_turnover) - Number(progress.amount_to_next_tier));
  const ringStyle = { "--progress": `${percent}%` } as CSSProperties;
  return <section className="tier-progress-card">
    <div className="tier-progress-top"><div><p className="eyebrow">ВАШ ПРОГРЕСС</p><h2>{isMaxLevel ? "Максимальный уровень" : `До ${progress.next_tier?.cashback_percent}% кешбэка`}</h2></div></div>
    <div className="tier-progress-main"><div className="progress-ring" style={ringStyle}><div><strong>{isMaxLevel ? `${progress.current_tier.cashback_percent}%` : `${percent.toFixed(0)}%`}</strong><small>{isMaxLevel ? "кешбэк" : "пройдено"}</small></div></div><div className="progress-copy"><strong>{isMaxLevel ? "Весь путь пройден" : <>Пройдено <Money value={completed} /></>}</strong><p>{isMaxLevel ? "Ваш максимальный кешбэк уже активен." : <>Осталось <Money value={progress.amount_to_next_tier} /> до следующего уровня</>}</p></div></div>
    <button type="button" className="program-link" onClick={onProgram}><span>Про программу лояльности</span><i><Icon name="arrow" size={17} /></i></button>
  </section>;
}
