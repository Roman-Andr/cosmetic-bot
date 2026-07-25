import type { CSSProperties } from "react";

import type { TierProgress } from "../../../entities/loyalty/model/types";
import { formatByn } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";

export function TierProgressCard({ progress, onHistory }: { progress: TierProgress; onHistory: () => void }) {
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const isMaxLevel = progress.next_tier === null;
  const ringStyle = { "--progress": `${percent}%` } as CSSProperties;
  return <section className="tier-progress-card">
    <div className="tier-progress-top"><div><p className="eyebrow">ВАШ ПУТЬ В VELINA CLUB</p><h2>{isMaxLevel ? "Максимальный уровень" : `До ${progress.next_tier?.cashback_percent}% осталось`}</h2></div><button type="button" className="history-link" onClick={onHistory}>История <Icon name="arrow" size={16} /></button></div>
    <div className="tier-progress-main"><div className="progress-ring" style={ringStyle}><div><strong>{isMaxLevel ? `${progress.current_tier.cashback_percent}%` : `${percent.toFixed(0)}%`}</strong><small>{isMaxLevel ? "кешбэк" : "пройдено"}</small></div></div><div className="progress-copy"><strong>{isMaxLevel ? `Ваш кешбэк ${progress.current_tier.cashback_percent}%` : formatByn(progress.amount_to_next_tier)}</strong><p>{isMaxLevel ? "Вы достигли лучшего уровня программы." : "ещё покупок до следующего уровня"}</p><span><Icon name="sparkle" size={16} />Оборот учитывается полностью</span></div></div>
    <ul className="tier-ladder">{progress.tiers.map((tier) => {
      const isCurrent = tier.minimum_turnover === progress.current_tier.minimum_turnover && tier.cashback_percent === progress.current_tier.cashback_percent;
      const isReached = Number(tier.minimum_turnover) <= Number(progress.current_tier.minimum_turnover);
      return <li className={`${isCurrent ? "current" : ""}${isReached ? " reached" : ""}`} key={`${tier.minimum_turnover}-${tier.cashback_percent}`}><i>{isReached ? <Icon name="check" size={13} /> : null}</i><span>{formatByn(tier.minimum_turnover)}</span><b>{tier.cashback_percent}%</b></li>;
    })}</ul>
  </section>;
}
