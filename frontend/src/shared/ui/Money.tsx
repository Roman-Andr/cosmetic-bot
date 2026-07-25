import { formatAmount } from "../lib/format";

export function CurrencySymbol({ className = "" }: { className?: string }) {
  return <img className={`currency-symbol ${className}`.trim()} src="/byn-symbol.svg" alt="" aria-hidden="true" />;
}

export function Money({ value, prefix = "", className = "" }: { value: string | number; prefix?: string; className?: string }) {
  return <span className={`money ${className}`.trim()} aria-label={`${prefix}${formatAmount(value)} белорусских рублей`}><span>{prefix}{formatAmount(value)}</span><CurrencySymbol /></span>;
}
