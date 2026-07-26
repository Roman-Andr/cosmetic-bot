import type { CSSProperties } from "react";

import type { TierProgress } from "../../../entities/loyalty/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Money } from "../../../shared/ui/Money";

export function TierProgressCard({ progress, onProgram }: { progress: TierProgress; onProgram: () => void }) {
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const isMaxLevel = progress.next_tier === null;
  const ringStyle = { "--progress": `${percent}%` } as CSSProperties;

  return <button type="button" className="benefit-progress-card" onClick={onProgram} aria-label={isMaxLevel ? "Открыть бонусную программу: максимальный уровень" : `Открыть бонусную программу: до следующего уровня осталось купить на ${progress.amount_to_next_tier}`}>
    <div className="benefit-progress-heading"><p>Как получить больше выгоды?</p><i><Icon name="arrow" size={16} /></i></div>
    <div className="benefit-progress-body"><div className="progress-ring" style={ringStyle}><div><strong>{isMaxLevel ? <Icon name="check" size={21} /> : `${percent.toFixed(0)}%`}</strong><small>{isMaxLevel ? "максимум" : "пройдено"}</small></div></div><div><strong>{isMaxLevel ? "Максимальный кешбэк уже активен" : <>Купите ещё на <Money value={progress.amount_to_next_tier} /></>}</strong><small>{isMaxLevel ? `${progress.current_tier.cashback_percent}% на все покупки` : `и получите ${progress.next_tier?.cashback_percent}% кешбэка`}</small></div></div>
  </button>;
}
