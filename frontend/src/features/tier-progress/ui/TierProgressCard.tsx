import type { CSSProperties } from "react";

import type { TierProgress } from "../../../entities/loyalty/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

export function TierProgressCard({ progress, onProgram }: { progress: TierProgress; onProgram: () => void }) {
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const isMaxLevel = progress.next_tier === null;
  const ringStyle = { "--progress": `${percent}%` } as CSSProperties;

  return <button type="button" className={ui("benefit-card", "benefit-progress-card")} onClick={onProgram} aria-label={isMaxLevel ? "Открыть бонусную программу: максимальный уровень" : `Открыть бонусную программу: до следующего уровня осталось купить на ${progress.amount_to_next_tier}`}>
    <div className={ui("benefit-progress-heading")}><p>Как получить ещё больше выгоды?</p></div>
    <div className={ui("benefit-progress-body")}><div className={ui("progress-ring", "progress-ring-background")} style={ringStyle}><div><strong>{isMaxLevel ? <Icon name="check" size={21} /> : `${percent.toFixed(0)}%`}</strong>{isMaxLevel && <small>максимум</small>}</div></div><div><strong>{isMaxLevel ? "Максимальный кешбэк уже активен" : <>Купите ещё на <Money value={progress.amount_to_next_tier} /></>}</strong><small>{isMaxLevel ? `${progress.current_tier.cashback_percent}% на все покупки` : `и получите ${progress.next_tier?.cashback_percent}% кешбэка`}</small></div></div>
  </button>;
}
