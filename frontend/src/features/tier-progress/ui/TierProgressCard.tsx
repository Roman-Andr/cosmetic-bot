import type { CSSProperties } from "react";

import type { TierProgress } from "../../../entities/loyalty/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Money } from "../../../shared/ui/Money";

export function TierProgressCard({ progress, onProgram }: { progress: TierProgress; onProgram: () => void }) {
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const isMaxLevel = progress.next_tier === null;
  const ringStyle = { "--progress": `${percent}%` } as CSSProperties;
  return <section className="tier-progress-card">
    <div className="tier-progress-top"><div><p className="eyebrow">ВАШ ПРОГРЕСС</p><h2>{isMaxLevel ? "Максимальный уровень" : `До ${progress.next_tier?.cashback_percent}% кешбэка`}</h2></div></div>
    <div className="tier-progress-main"><div className="progress-ring" style={ringStyle} aria-label={isMaxLevel ? "Достигнут максимальный уровень" : `Прогресс до следующего уровня: ${percent.toFixed(0)}%`}><div><strong>{isMaxLevel ? `${progress.current_tier.cashback_percent}%` : <Icon name="sparkle" size={20} />}</strong><small>{isMaxLevel ? "кешбэк" : "ваш путь"}</small></div></div><div className="progress-copy"><strong>{isMaxLevel ? "Максимальный уровень активен" : <>Осталось купить на <Money value={progress.amount_to_next_tier} /></>}</strong><p>{isMaxLevel ? `Ваш кешбэк — ${progress.current_tier.cashback_percent}%.` : "до следующего уровня лояльности"}</p></div></div>
    <button type="button" className="program-link" onClick={onProgram}><span>Про программу лояльности</span><i><Icon name="arrow" size={17} /></i></button>
  </section>;
}
