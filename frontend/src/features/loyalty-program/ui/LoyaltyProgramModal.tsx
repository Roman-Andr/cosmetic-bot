import type { Profile } from "../../../entities/loyalty/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

const tierCardClasses = {
  current: ui("tier-status-card", "tier-status-current"),
  reached: ui("tier-status-card", "tier-status-reached"),
  locked: ui("tier-status-card"),
} as const;

const tierNameClasses = {
  current: ui("tier-status-name", "tier-name-current"),
  reached: ui("tier-status-name"),
  locked: ui("tier-status-name", "tier-name-locked"),
} as const;

function tierTitle(index: number, total: number): string {
  if (index === 0) return "Базовый";
  if (index === total - 1) return "Премиум";
  if (total === 3) return "Стандарт";
  return `Уровень ${index + 1}`;
}

export function LoyaltyProgramModal({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const progress = profile.tier_progress;
  const turnover = Number(profile.lifetime_turnover);
  const currentTierIndex = progress.tiers.findIndex((tier) =>
    Number(tier.minimum_turnover) === Number(progress.current_tier.minimum_turnover)
    && Number(tier.cashback_percent) === Number(progress.current_tier.cashback_percent));

  return <Modal title="Программа лояльности" onClose={onClose}>
    <section className={ui("program-levels-view")}>
      <div className={ui("program-pane-heading")}><div><p className={ui("overline")} data-overline>СТАТУСЫ</p><h3>Уровни программы</h3></div></div>
      <ul className={ui("tier-status-list")}>{progress.tiers.map((tier, index) => {
        const isCurrent = index === currentTierIndex;
        const isReached = currentTierIndex >= 0
          ? index <= currentTierIndex
          : Number(tier.minimum_turnover) <= Number(progress.current_tier.minimum_turnover);
        const threshold = Number(tier.minimum_turnover);
        const previousThreshold = index === 0 ? 0 : Number(progress.tiers[index - 1].minimum_turnover);
        const tierRange = threshold - previousThreshold;
        const unlockProgress = tierRange <= 0 ? 100 : Math.min(100, Math.max(0, ((turnover - previousThreshold) / tierRange) * 100));
        const amountRemaining = Math.max(0, threshold - turnover);
        const state = isCurrent ? "current" : isReached ? "reached" : "locked";

        return <li className={tierCardClasses[state]} key={`${tier.minimum_turnover}-${tier.cashback_percent}`}>
          <div className={ui("tier-status-head")}>
            <div className={tierNameClasses[state]}>
              <span><Icon name={isReached ? "check" : "lock"} size={15} /></span>
              <div><strong>{tierTitle(index, progress.tiers.length)}</strong><small>{isCurrent ? "Активный уровень" : isReached ? "Уровень открыт" : "Пока недоступен"}</small></div>
            </div>
            <span className={ui("tier-reward")}><b>{tier.cashback_percent}%</b><small>кешбэк</small></span>
          </div>
          <p>Начисляется на сумму, оплаченную деньгами</p>
          {isCurrent && <div className={ui("tier-status-note", "tier-note-current")}><Icon name="sparkle" size={14} />Действует для следующих покупок</div>}
          {isReached && !isCurrent && <div className={ui("tier-status-note")}><Icon name="check" size={14} />Открыт при обороте от <Money value={tier.minimum_turnover} /></div>}
          {!isReached && <div className={ui("tier-unlock")}>
            <div className={ui("tier-progress-line")}><i style={{ width: `${unlockProgress}%` }} /></div>
            <span>Купите ещё на <Money value={amountRemaining} /></span>
          </div>}
        </li>;
      })}</ul>
    </section>
  </Modal>;
}
