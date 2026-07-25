import type { CSSProperties } from "react";

import type { TierProgress } from "../../../entities/loyalty/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Money } from "../../../shared/ui/Money";

export function TierProgressCard({ progress, onProgram }: { progress: TierProgress; onProgram: () => void }) {
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const isMaxLevel = progress.next_tier === null;
  const ringStyle = { "--progress": `${percent}%` } as CSSProperties;

  return <section className="journey-card">
    <div className="journey-card-heading"><div><p className="eyebrow">ВАШ УРОВЕНЬ</p><h2>{isMaxLevel ? "Максимальный кешбэк" : `Путь к ${progress.next_tier?.cashback_percent}%`}</h2></div><span>{progress.current_tier.cashback_percent}%</span></div>
    <div className="journey-card-body">
      <div className="progress-ring" style={ringStyle} aria-label={isMaxLevel ? "Достигнут максимальный уровень" : `Прогресс до следующего уровня: ${percent.toFixed(0)}%`}><div><strong>{isMaxLevel ? <Icon name="check" size={22} /> : <Icon name="sparkle" size={20} />}</strong><small>{isMaxLevel ? "готово" : "уровень"}</small></div></div>
      <div className="journey-copy"><strong>{isMaxLevel ? "Вы на вершине программы" : <>Осталось купить на <Money value={progress.amount_to_next_tier} /></>}</strong><p>{isMaxLevel ? "Ваш максимальный кешбэк уже активен." : "Следующая покупка приблизит новый уровень."}</p></div>
    </div>
    <button type="button" className="journey-link" onClick={onProgram}><span>Все уровни и история баллов</span><i><Icon name="arrow" size={16} /></i></button>
  </section>;
}
